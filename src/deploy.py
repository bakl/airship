#!/usr/bin/env python3

### START OF CODE
import os
import sys
import re
import signal
import subprocess
import json
import http.client
import pprint
from datetime import datetime

version = "v1.2.40"

import config

# Global flags
debug_flag = False
dry_run_flag = False
skip_containers_flag = False
update_flag = False
config_flag = False
version_flag = False

# -- Lib

def usage():
    print("AirShip [%s] usage: deploy.py [server name] {commands} {options}" % version)
    print("")
    print("Commands: ")
    print(" build-env  build environment content")
    print(" build      build docker containers")
    print(" push       push docker containers to registry")
    print(" deploy     make environment archive, upload it to server, and run")
    print(" run        execute 'run' command")
    print("")
    print("Options: ")
    print(" -v                   verbose mode, print executed commands")
    print(" --dry                dry run mode, all commands will not executed")
    print(" --skip-containers    skip build, deploy and import docker containers")
    print("")
    print(" --version            print this script version")
    print(" --update             update this script")
    print(" --config             print config")

# -- Lib

def mes(text):
    print('\033[92m# [' + datetime.now().strftime('%H:%M:%S.%f') + '] ' + text + '\033[0m')


def err(text):
    print('\033[91m# ' + text + '\033[0m')


def deb(text):
    if not debug_flag:
        return
    print('\033[90m' + text + '\033[0m')


def run(command, input=None):
    if input is not None:
        deb(command + " " + str(input))
    else:
        deb(command)
    if not dry_run_flag:
        try:
            process = subprocess.run(command, input=input, shell=True, text=True)
            if process.returncode < 0 or process.returncode > 0:
                sys.exit(process.returncode)
        except OSError as e:
            print("Execution failed:", e, file=sys.stderr)


def ssh(server, command):
    cmd = "ssh "

    if 'port' in server and server['port'] != '':
        cmd += " -p " + server['port'] + " "

    if 'user' in server and server['user'] != '':
        cmd += server['user'] + "@"

    cmd += server['host']
    cmd += " bash -s"
    run(cmd, command)


def upload(server, frm, to, ignore_existing=False):
    cmd = "rsync -chavzP --info=progress2"

    if ignore_existing:
        cmd += " --ignore-existing"

    cmd += " -e 'ssh"

    if 'port' in server and server['port'] != '':
        cmd += " -p " + server['port']

    cmd += "' " + frm + " "

    if 'user' in server and server['user'] != '':
        cmd += server['user'] + "@"

    cmd += server['host'] + ":" + to
    run(cmd)


def archive(destination_dir, path):
    if os.path.isdir(path):
        run("cd %s && tar -zcf %s --totals -C %s ." % (path, destination_dir, path))
    else:
        file = os.path.basename(path)
        path = os.path.dirname(path)
        run("cd %s && tar -zcf %s --totals -C %s %s" % (path, destination_dir, path, file))


def copy_dir(file):
    run("cp -R %s %s" % (file['path'], file['env_path']))


def copy_and_replace(variables, file):
    cmdVars = ""

    if not os.path.exists(os.path.dirname(file['env_path'])):
        run("mkdir -p %s" % os.path.dirname(file['env_path']))

    if 'replace_vars' in file and file['replace_vars'] and len(variables) > 0:
        for var, val in variables.items():
            cmdVars += " -e 's/${%s}/%s/g'" % (var, val.replace('/', r'\/'))
        cmd = "cat %s | sed %s > %s" % (file['path'], cmdVars, file['env_path'])
    else:
        cmd = "cp %s %s" % (file['path'], file['env_path'])
    run(cmd)


def replace_variables(variables, str):
    for var, val in variables.items():
        str = str.replace("$" + var, val)
    return str


def find_files_for_replace(path, patterns):
    fileCandidates = []
    for root, subdirs, files in os.walk(path):
        for file in files:
            if not re.findall("(%s)" % "|".join(patterns), file):
                continue
            fileCandidates.append(os.path.join(root, file))

    return fileCandidates


def docker_build(variables, container):
    build_variables = variables
    build_variables['DOCKERFILE_DIR'] = os.path.dirname(container['dockerfile'])

    container['name'] = replace_variables(variables, container['name'])
    container['registry'] = replace_variables(variables, container['registry'])
    container['dockerfile'] = os.path.join(config.work_dir, replace_variables(variables, container['dockerfile']))

    build_args = []
    for arg in container['build_args']:
        arg = replace_variables(build_variables, arg)
        build_args.append('--build-arg ' + arg)

    build_contexts = []
    if 'build_contexts' in container:
        for arg in container['build_contexts']:
            arg = replace_variables(build_variables, arg)
            build_args.append('--build-context ' + arg)

    if container['build_path'] == "./":
        container['build_path'] = os.path.dirname(container['dockerfile'])
    else:
        container['build_path'] = os.path.join(config.work_dir, replace_variables(variables, container['build_path']))

    buildx = ''
    if ('buildx' in config.docker and config.docker['buildx']) or ('buildx' in container and container['buildx']):
        buildx = 'buildx'

    platform = ''
    if 'platform' in config.docker:
        platform = '--platform ' + config.docker['platform']
    if 'platform' in container:
        platform = '--platform ' + container['platform']

    run("%sdocker %s build %s %s %s -t %s/%s -f %s %s" % (
        get_docker_host(variables, container['docker_host'] if 'docker_host' in container else ''),
        buildx,
        platform,
        " ".join(build_args),
        " ".join(build_contexts),
        container['registry'],
        container['name'],
        container['dockerfile'],
        container['build_path'],
    ))


def docker_push(variables, container):
    container['registry'] = replace_variables(variables, container['registry'])
    container['name'] = replace_variables(variables, container['name'])
    run("%sdocker push %s/%s" % (
        get_docker_host(variables, container['docker_host'] if 'docker_host' in container else ''),
        container['registry'],
        container['name']
    ))


def docker_dump(variables, container):
    container['registry'] = replace_variables(variables, container['registry'])
    container['name'] = replace_variables(variables, container['name'])

    temp_path = config.temp_dir_environment
    if 'deploy_separately' in container and container['deploy_separately']:
        temp_path = config.temp_dir_containers

    run("%sdocker save %s/%s -o %s" % (
        get_docker_host(variables, container['docker_host'] if 'docker_host' in container else ''),
        container['registry'],
        container['name'],
        os.path.join(temp_path, replace_variables(variables, container['arch_name']))
    ))

def docker_cleanup_old_versions(server, variables, container):
    """Clean up old versions of Docker images"""
    if not container.get('cleanup_old', False):
        deb(f"Cleanup disabled for {container['name']}")
        return

    registry = container.get('registry', '')
    image_name = replace_variables(variables, container['name'].split(':')[0])
    if registry:
        image_name = f"{registry}/{image_name}"
    
    keep_versions = container.get('keep_versions', 2)
    cleanup_pattern = replace_variables(variables, container.get('cleanup_pattern', ''))
    
    # Convert glob pattern to grep pattern
    if cleanup_pattern:
        cleanup_pattern = cleanup_pattern.replace('*', '.*')
    
    mes(f"Cleaning up old versions of {image_name}" + 
        (f" matching pattern '{cleanup_pattern}'" if cleanup_pattern else '') +
        f" (keeping {keep_versions} newest versions)")

    cleanup_script = f"""set -e

echo "Listing all tags for {image_name}..."
ALL_TAGS=$(docker images '{image_name}' --format '{{{{.Tag}}}}' | sort -rV)

if [ -z "$ALL_TAGS" ]; then
    echo "No tags found"
    exit 0
fi

# Filter tags by pattern if specified
if [ ! -z "{cleanup_pattern}" ]; then
    echo "Filtering tags by pattern: {cleanup_pattern}"
    ALL_TAGS=$(echo "$ALL_TAGS" | grep -E "{cleanup_pattern}" || true)
    if [ -z "$ALL_TAGS" ]; then
        echo "No tags match the pattern"
        exit 0
    fi
fi

TOTAL_TAGS=$(echo "$ALL_TAGS" | wc -l)
echo "Found $TOTAL_TAGS matching tags"

if [ $TOTAL_TAGS -gt {keep_versions} ]; then
    echo "Keeping {keep_versions} newest versions, removing older ones..."
    TAGS_TO_REMOVE=$(echo "$ALL_TAGS" | tail -n +$(({keep_versions} + 1)))
    echo "$TAGS_TO_REMOVE" | while read -r tag; do
        if [ ! -z "$tag" ]; then
            # Check if image is used by any container
            if docker ps -a --format '{{{{.Image}}}}' | grep -q "{image_name}:$tag"; then
                echo "Skipping $tag - image is in use"
                continue
            fi
            echo "Removing {image_name}:$tag"
            if docker rmi -f {image_name}:$tag; then
                echo "Successfully removed $tag"
            else
                echo "Failed to remove $tag"
            fi
        fi
    done
else
    echo "No cleanup needed - number of tags ($TOTAL_TAGS) <= keep_versions ({keep_versions})"
fi"""
    
    try:
        ssh(server, cleanup_script)
    except Exception as e:
        err(f"Failed to cleanup old versions of {image_name}: {str(e)}")
        # Don't fail deployment if cleanup fails
        pass


def docker_import(server, variables, container):
    mes("Import container: %s" % container['name'])
    ssh(server, "cd %s && docker load -i %s" % (
        config.destination_dir,
        replace_variables(variables, container['arch_name'])
    ))


def user_commands(server, variables, commands, place):
    if place == 'remote':
        for command in commands:
            ssh(server, replace_variables(variables, command))
    else:
        for command in commands:
            run(replace_variables(variables, command))


def stage_cleanup_temp_dir():
    mes("Create / cleanup temp directory")
    run("mkdir -p %s" % config.temp_dir)
    run("rm -rf %s/*" % (config.temp_dir))
    run("mkdir -p %s" % config.temp_dir_environment)
    run("mkdir -p %s" % config.temp_dir_containers)
    run("mkdir -p %s" % config.temp_dir_archives)

def get_docker_host(variables, host = ''):
    docker_host = ''
    if host != '':
        docker_host = host
    elif 'host' in config.docker:
        docker_host = config.docker['host']
    else:
        return ''

    return 'DOCKER_HOST=' + replace_variables(variables, docker_host) + ' '

def http_request(url):
    (host, path) = url.split('/', 1)
    conn = http.client.HTTPSConnection(host)
    conn.request('GET', '/' + path, None, {'User-agent': 'AirShip'})
    return conn.getresponse().read().decode()
    print(response)


def update():
    resp = http_request('api.github.com/repos/bakl/airship/git/refs/tags/')
    tags = json.loads(resp)
    latest_tag_name = tags[len(tags)-1]['ref'].replace('refs/tags/', '')
    current_version = version.replace('v', '').replace('.', '')
    latest_version = latest_tag_name.replace('v', '').replace('.', '')
    if latest_version == current_version or latest_version < current_version:
        mes("Newest version %s is here!" % version)
        exit()

    code = http_request("raw.githubusercontent.com/bakl/airship/%s/src/deploy.py" % latest_tag_name)

    if '### END OF CODE' not in code or '### START OF CODE' not in code:
        err("Downloaded code is broken. Check github repository issues or try again.")
        exit()

    ask = input("Newest version is %s. Start update Y/n: " % latest_tag_name)
    if ask != "Y" and ask != "y" and ask != "":
        exit()

    f = open(sys.argv[0], "w")
    f.write(code)
    f.close()

    mes("AirShip updated to %s" % latest_tag_name)


def init_config(server_name=''):
    """Initialize configuration based on server name"""
    global server

    # Load env to variables
    config.variables.update(os.environ)

    # Set server name in variables
    config.variables['SERVER_NAME'] = server_name

    # Load server config
    if server_name != '':
        server = config.servers[server_name]

        config.variables.update(
            {
                'SERVER_HOST': server['host'],
                'VERSION': replace_variables(config.variables, server['version']),
                'ENV': server['env'],
            }
        )

        if 'variables' in server:
            config.variables.update(server['variables'])

        if "destination_dir" in server:
            config.destination_dir = server['destination_dir']

    config.destination_dir = replace_variables(config.variables, config.destination_dir)
    config.temp_dir = replace_variables(config.variables, config.temp_dir)

    config.temp_dir_environment = os.path.join(config.temp_dir, "environment")
    config.temp_dir_containers = os.path.join(config.temp_dir, "containers")
    config.temp_dir_archives = os.path.join(config.temp_dir, "archives")

    config.variables.update(
        {
            'DESTINATION_DIR': config.destination_dir,
            'TEMP_DIR': config.temp_dir,
            'TEMP_ENVIRONMENT_DIR': config.temp_dir_environment
        }
    )

    config.arch_name = replace_variables(config.variables, config.arch_name)

    if skip_containers_flag:
        config.containers = []

    if not hasattr(config, 'docker'):
        config.docker = {}

def signal_handler(signal, frame):
    sys.exit(0)

signal.signal(signal.SIGINT, signal_handler)

def main():
    """Main function to run the deployment process"""
    global commands, server_name, debug_flag, dry_run_flag, skip_containers_flag, update_flag, config_flag, version_flag

    # Initialize variables
    commands = []
    server_name = ""
    commands_str = ""
    flags = []

    for i, arg in enumerate(sys.argv):
        if arg[0] == "-":
            flags.append(arg)
        elif i > 0 and server_name == "":
            server_name = arg
        elif i > 0 and commands_str == "":
            commands_str = arg

    if commands_str != "":
        commands = commands_str.strip('').split(",")

    debug_flag = "-v" in flags
    dry_run_flag = "--dry" in flags
    skip_containers_flag = "--skip-containers" in flags
    update_flag = "--update" in flags
    config_flag = "--config" in flags
    version_flag = "--version" in flags

    # Initialize configuration
    init_config(server_name)

    if len(sys.argv) < 2:
        usage()
        exit()

    if 'run' in commands or 'deploy' in commands or 'build' in commands or 'build-env' in commands or 'push' in commands or 'init' in commands:
        if len(sys.argv) < 3:
            usage()
            exit()
        if server_name not in config.servers:
            err("Error: server [%s] not exist in config" % server_name)
            exit()

    if update_flag:
        commands = ['update']

    if version_flag:
        commands = ['version']

    if config_flag:
        commands = ['config']

    if len(commands) < 1:
        ask = input("Do you want to build, push and deploy v%s to [%s] Y/n: " % (config.variables['VERSION'], server_name))
        if ask == "Y" or ask == "y" or ask == "":
            commands = ['build-env', 'build', 'push', 'deploy']
        else:
            exit()


    # Print welcome message
    print("AirShip %s takes of...\n%s" % (version, getattr(config, 'motd', '')))

    # -- Commands
    for command in commands:
        if command == 'version':
            mes("Current version is %s" % version)

        elif command == 'update':
            mes("Checking for updates...")
            update()

        elif command == 'build-env':
            stage_cleanup_temp_dir()

            mes("Copy environment files")
            for file in config.files:
                file['path'] = os.path.join(config.work_dir, file['path'])
                file['path'] = replace_variables(config.variables, file['path'])

                file['env_path'] = os.path.join(config.temp_dir_environment, file['env_path'])
                file['env_path'] = replace_variables(config.variables, file['env_path'])

                if not os.path.exists(file['path']) and not dry_run_flag:
                    err("File/dir %s not exist" % file['path'])
                    continue

                deb("Process file/dir: " + file['path'])
                if os.path.isfile(file['path']):
                    # @TODO mkdir?
                    copy_and_replace(config.variables, file)

                if os.path.isdir(file['path']):
                    copy_dir(file)

                    if 'replace_vars' in file and file['replace_vars']:
                        for dirFile in find_files_for_replace(file['path'], config.replace_vars_file_patterns):
                            copy_and_replace(
                                config.variables,
                                {
                                    'path': dirFile,
                                    'replace_vars': True,
                                    'env_path': os.path.join(config.temp_dir_environment, file['env_path'],
                                                             os.path.relpath(dirFile, file['path']))
                                }
                            )

        elif command == 'build':
            mes("Start building v%s for [%s]" % (config.variables['VERSION'], server_name))

            mes("Build containers")
            for container in config.containers:
                docker_build(config.variables, container)

        elif command == 'push':
            mes("Start pushing containers v%s for [%s]" % (config.variables['VERSION'], server_name))
            mes("Push containers")
            for container in config.containers:
                if 'arch_name' not in container:
                    docker_push(config.variables, container)

        elif command == 'deploy':
            mes("Start deploy v%s to [%s]" % (config.variables['VERSION'], server_name))

            deb("Variables: %r" % config.variables)

            mes("Dump containers")
            for container in config.containers:
                if 'arch_name' in container:
                    docker_dump(config.variables, container)

            mes("Build archive(s)")
            archive(os.path.join(config.temp_dir_archives, config.arch_name), config.temp_dir_environment)

            mes("Create destination dir [%s] on destination server" % config.destination_dir)
            ssh(server, "mkdir -p %s" % config.destination_dir)

            mes("Upload archive")
            upload(server, "%s/*" % config.temp_dir_archives, "%s/" % config.destination_dir)

            mes("Extract archive")
            ssh(server, "cd %s && tar -xzf %s --totals ." % (config.destination_dir, config.arch_name))

            for container in config.containers:
                if 'arch_name' in container:
                    temp_path = config.temp_dir_environment
                    if 'deploy_separately' in container and 'deploy_separately' in container and container['deploy_separately']:
                        temp_path = config.temp_dir_containers

                        temp_path = os.path.join(temp_path, replace_variables(config.variables, container['arch_name']))

                        excludeVariables = {}
                        for var, val in config.variables.items():
                            excludeVariables[var] = "*[^" + val + "]"

                        if 'remove_old' in container and container['remove_old']:
                            ssh(server, "rm -f " + os.path.join(config.destination_dir,
                                                                replace_variables(excludeVariables, container['arch_name'])))

                        upload(server, temp_path, config.destination_dir,
                               'ignore_existing' in container and container['ignore_existing'])
                    docker_import(server, config.variables, container)

                    docker_cleanup_old_versions(server, config.variables, container)

            mes("Run")
            ssh(server, replace_variables(config.variables, config.run_command))

        elif command == 'run':
            mes("Run")
            ssh(server, replace_variables(config.variables, config.run_command))

        elif command == 'config':
            mes("Current config")
            pprint.pprint({var:vars(config)[var] for var in dir(config) if not var.startswith('_')})

        else:
            if hasattr(config, 'user_commands'):
                if command in config.user_commands:
                    mes("Start user command: %s, %s, server [%s]" % (command, config.user_commands[command]['place'], server_name))
                    user_commands(
                        server,
                        config.variables,
                        config.user_commands[command]['commands'],
                        config.user_commands[command]['place']
                    )

if __name__ == '__main__':
    main()

### END OF CODE
