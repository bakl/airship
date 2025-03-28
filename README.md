# AirShip Deploy Script

## Overview

The AirShip deploy script is a flexible tool designed to facilitate the deployment of various projects, including Docker-based projects. It supports building, pushing, and deploying Docker containers, managing environment files, and executing user-defined commands on local or remote servers.

## Features

- Build and push Docker containers
- Create and upload environment archives
- Extract archives and run commands on remote servers
- Support for variable replacements in file paths and contents
- Customizable via a configuration file
- Handles updates to the script from a remote repository
- Can be used for projects without Docker containers

## Installation

1. Download the deploy script using `curl`:
    ```sh
    curl -o deploy.py https://raw.githubusercontent.com/bakl/airship/refs/heads/main/src/deploy.py
    curl -o config.py https://raw.githubusercontent.com/bakl/airship/refs/heads/main/src/config.py
    ```

2. Ensure the script is executable:
    ```sh
    chmod +x deploy.py
    ```

## Usage

The deploy script supports several commands and options. Below is a comprehensive guide to using the script.

### Basic usage

```sh
./deploy.py [server name] {commands} {options}
```

### Available Commands

- deploy: Common command to deploy project
  - Make environment archive`[build-env]`,
  - Build and push containers`[build] + [push]`
  - upload it to the server
  - and run `[run]`

But you can run separate command using: 
- build-env: Build environment content
- build: Build Docker containers
- push: Push Docker containers to the registry
- run: Execute the run command specified in the configuration

### Available Options
- -v: Verbose mode, print executed commands
- --dry: Dry run mode, commands will not be executed
- --skip-containers: Skip build, deploy, and import Docker containers [deprecated]
- --version: Print the script version
- --update: Update the script to the latest version from the remote repository
- --config: Print the current configuration

### Example Commands
Deploy to Development Server
```sh
./deploy.py dev deploy
```

Build and Push Docker Containers
```sh
./deploy.py dev build push
```

Run Custom Command
```sh
./deploy.py dev run
```

Check for Updates
```sh
./deploy.py --update
```

## Docker Container Delivery Options
The script supports multiple options for delivering Docker containers:

#### Using arch_name:

If arch_name is defined for a container, the container image will be delivered over SSH to the remote server and then imported.

Example:
```python
containers = [
    {
    'name': 'fish-first-container:$VERSION',
    'registry': 'registry.fish.com:5000',
    'dockerfile': 'docker/fish/Dockerfile',
    'arch_name': 'fish-first-container.tar',
    'docker_host': 'ssh://user@remote-ssh-docker-host-another',
    'cleanup_old': true,  # Optional: enable cleanup of old versions (default: false)
    'keep_versions': 5,   # Optional: number of versions to keep (default: 3)
    'cleanup_pattern': '*-prod'  # Optional: pattern to match tags for cleanup (default: *-{build_type})
    }
]
```

#### Using Docker Registry:

If arch_name is not defined, the container will be pushed to the registry and pulled on the remote server using the user's Docker Compose or run script.

Example:
```python
containers = [
    {
    'name': 'fish-second-container:$VERSION',
    'registry': 'registry.fish.com:5000',
    'dockerfile': 'docker/fish-second/Dockerfile'
    }
]
```

#### Defining Docker Host:

You can build container images directly on the production server or on a separate build server but not locally by specifying the docker_host.

 Example:
```python
containers = [
    {
    'name': 'fish-third-container:$VERSION',
    'registry': 'registry.fish.com:5000',
    'dockerfile': 'docker/fish-third/Dockerfile',
    'docker_host': 'ssh://user@remote-ssh-docker-host'
    }
]
```

## Configuration
The configuration file defines the settings and variables for the deploy script. Below is an example configuration file with comments explaining each section.

```python
# Base path for all local paths
work_dir = '../'

# Temporary directory for building environment archive
temp_dir = "/tmp/fish-deploy-tmp"

# Env archive file name
arch_name = "fish.dist.tar.gz"

# Directory on the destination server for extracting the environment
destination_dir = "fish"

# Variables
# Built-in variables: VERSION, ENV, DESTINATION_DIR, DOCKER_PROJECT_NAME, TEMP_DIR, TEMP_ENVIRONMENT_DIR
# Use $VARNAME variables in paths and ${VARNAME} in file contents
variables = {
    'DOCKER_PROJECT_NAME': 'fish',
    'SUDO': 'sudo'
}

# Replace content variables only if file name matches pattern
replace_vars_file_patterns = ['.conf$', '.yml$', 'default$']

# Run command to start the project on the destination server
run_command = "cd $DESTINATION_DIR && docker-compose -p $DOCKER_PROJECT_NAME up -d"

# Docker configuration
# You can set up buildx, platform, docker host options on global and container levels
docker = {
    'host': 'ssh://user@remote-ssh-docker-host', # Global Docker host
    'buildx': False,  # Global buildx option
    'platform': 'linux/amd64'  # Global platform
}

# List of Docker containers to build and deploy
containers = [
    {
        'name': 'fish-first-container:$VERSION',  # Name of the container with version variable
        'registry': 'registry.fish.com:5000',  # Docker registry URL
        'dockerfile': 'docker/fish/Dockerfile',  # Path to Dockerfile
        'build_path': '',  # Build path (empty means use directory of Dockerfile)
        'build_args': ['VERSION=$VERSION'],  # Build arguments
        'build_contexts': ['app1=/path/to/app1-src-dir'],  # Build contexts
        'arch_name': 'fish-first-container.tar',  # Archive name for the container
        'buildx': True,  # Use buildx for this container
        'platform': 'linux/amd64',  # Platform for this container
        'docker_host': 'ssh://user@remote-ssh-docker-host-another',  # Docker host for this container
        'cleanup_old': True,  # Optional: enable cleanup of old versions (default: false)
        'keep_versions': 5,   # Optional: number of versions to keep (default: 3)
        'cleanup_pattern': '*-prod'  # Optional: pattern to match tags for cleanup (default: *-{build_type})
    },
    {
        'name': 'fish-second-container:$VERSION',
        'registry': 'registry.fish.com:5000',
        'dockerfile': 'docker/fish-second/Dockerfile',
        'build_path': 'docker/fish-second',
        'build_args': ['VERSION=$VERSION', 'ENV=$ENV']
    },
    {
        'name': 'fish-third-container:$VERSION',
        'registry': 'registry.fish.com:5000',
        'dockerfile': 'docker/fish-third/Dockerfile',
        'docker_host': 'ssh://user@remote-ssh-docker-host'
    }
]

# Environment files or directories to be included in the deployment
files = [
    {'path': 'docker/docker-compose.yml', 'env_path': 'docker-compose.yml', 'replace_vars': True},
    {'path': 'docker/nginx', 'env_path': 'nginx', 'replace_vars': True},
    {'path': 'config/config_$ENV.yml', 'env_path': 'config/config_$ENV.yml', 'replace_vars': True},
]

# User-defined commands to be executed locally or remotely
user_commands = {
    'init': {
        'place': 'remote',  # Commands to be executed on the remote server
        'commands': [
            '$SUDO apt-get update',
            '$SUDO apt-get install apt-transport-https ca-certificates curl software-properties-common',
        ]
    },
    'hello': {
        'place': 'local',  # Commands to be executed locally
        'commands': [
            'echo "hello world"'
        ],
    },
    'hello-remote': {
        'place': 'remote',  # Commands to be executed on the remote server
        'commands': [
            'echo "hello world on server: $SERVER_NAME"'
        ],
    }
}

# Server configurations
servers = {
    'dev': {
        'host': 'fish-dev',  # Hostname or IP address of the development server
        'version': '0.0.1',  # Version of the project
        'env': 'dev',  # Environment name (e.g., dev, prod)
        'destination_dir': 'fish',  # Directory on the server for the project
        'variables': {
            'DOMAIN': 'fish.local'  # Additional variables specific to the development server
        }
    },
    'prod': {
        'host': 'fish-prod',
        'version': '0.0.1',
        'env': 'prod',
        'destination_dir': 'fish',
        'variables': {
            'DOMAIN': 'fish.com',
            'SUDO': ''  # No sudo required for production
        }
    },
}
```

### Explanation of Config Sections
1. #### Base Paths and Directories:

   - `work_dir`: Base directory for local paths, which is '../' in this example.
   - `temp_dir`: Temporary directory for building the environment archive.
   - `arch_name`: Name of the archive file created during deployment.
   - `destination_dir`: Directory on the destination server where the environment will be extracted.
2. #### Variables:
    - `variables`: Dictionary of variables to be used in paths and file contents. This includes built-in variables and custom ones.
3. #### File Patterns for Variable Replacement:
    - `replace_vars_file_patterns`: List of regex patterns for file names. Only files matching these patterns will have their content variables replaced.
4. #### Run Command:
   - `run_command`: Command to be executed on the destination server to start the project. This uses Docker Compose to bring up services.
5. #### Docker Configuration:
   - `docker`: Global Docker settings, such as the Docker host, buildx usage, and platform. These settings can be overridden at the container level.
6. #### Containers:
   - `containers`: List of dictionaries defining Docker containers to be built and deployed. Each dictionary contains container-specific settings such as name, registry, Dockerfile path, build arguments, and build contexts.
7. #### Environment Files:
   - `files`: List of dictionaries defining environment files or directories to be included in the deployment. Each dictionary contains the local path, destination path, and whether variable replacement is needed.
8. #### User Commands:
   - `user_commands`: Dictionary of user-defined commands that can be executed either locally or remotely. Each command set includes the place (local or remote) and a list of commands to be executed.
9. #### Server Configurations:
   - `servers`: Dictionary defining different server environments (e.g., dev, prod). Each server configuration includes host, version, environment, destination directory, and any additional variables specific to the server.
   
## License
This project is licensed under the MIT License