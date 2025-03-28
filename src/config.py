# Base path for all local paths
work_dir = '../'

# Temporary directory for building environment archive
temp_dir = "/tmp/projectname-deploy-tmp"

# Env archive file name
arch_name = "projectname.dist.tar.gz"

# Directory on the destination server for extracting the environment
destination_dir = "projectname"

# Variables
# Built-in variables: VERSION, ENV, DESTINATION_DIR, DOCKER_PROJECT_NAME, TEMP_DIR, TEMP_ENVIRONMENT_DIR
# Use $VARNAME variables in paths and ${VARNAME} in file contents
variables = {
    'DOCKER_PROJECT_NAME': 'projectname',
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
        'name': 'projectname-first-container:$VERSION',  # Name of the container with version variable
        'registry': 'registry.projectname.com:5000',  # Docker registry URL
        'dockerfile': 'docker/projectname/Dockerfile',  # Path to Dockerfile
        'build_path': '',  # Build path (empty means use directory of Dockerfile)
        'build_args': ['VERSION=$VERSION'],  # Build arguments
        'build_contexts': ['app1=/path/to/app1-src-dir'],  # Build contexts
        'arch_name': 'projectname-first-container.tar',  # Archive name for the container
        'buildx': True,  # Use buildx for this container
        'platform': 'linux/amd64',  # Platform for this container
        'docker_host': 'ssh://user@remote-ssh-docker-host-another',  # Docker host for this container,
        'cleanup_old': True,  # Optional: enable cleanup of old versions (default: false)
        'keep_versions': 5,   # Optional: number of versions to keep (default: 3)
        'cleanup_pattern': '*-prod'  # Optional: pattern to match tags for cleanup (default: *-{build_type})
    },
    {
        'name': 'projectname-second-container:$VERSION',
        'registry': 'registry.projectname.com:5000',
        'dockerfile': 'docker/projectname-second/Dockerfile',
        'build_path': 'docker/projectname-second',
        'build_args': ['VERSION=$VERSION', 'ENV=$ENV'],
    }
]

# Environment files or directories to be included in the deployment
files = [
    {'path': 'docker/docker-compose.yml', 'env_path': 'docker-compose.yml', 'replace_vars': True},
    {'path': 'docker/nginx', 'env_path': 'nginx', 'replace_vars': True},
    {'path': 'docker/grafana', 'env_path': 'grafana', 'replace_vars': False},
    {'path': 'docker/influx', 'env_path': 'influx', 'replace_vars': False},
    {'path': 'docker/clickhouse', 'env_path': 'clickhouse', 'replace_vars': False},
    {'path': 'docker/telegraf', 'env_path': 'telegraf', 'replace_vars': False},
    {'path': 'config/config_$ENV.yml', 'env_path': 'config/config_$ENV.yml', 'replace_vars': True},
]

# User-defined commands to be executed locally or remotely
user_commands = {
    'init': {
        'place': 'remote',  # Commands to be executed on the remote server
        'commands': [
            # Install Docker
            '$SUDO apt-get update',
            '$SUDO apt-get install apt-transport-https ca-certificates curl software-properties-common',
            'curl -fsSL https://download.docker.com/linux/ubuntu/gpg | $SUDO apt-key add -',
            '$SUDO add-apt-repository "deb [arch=amd64] https://download.docker.com/linux/ubuntu $(lsb_release -cs) stable"',
            '$SUDO apt-get update',
            '$SUDO apt-get install docker-ce',

            # Install Docker Compose
            '$SUDO curl -L "https://github.com/docker/compose/releases/download/1.24.1/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose',
            '$SUDO chmod +x /usr/local/bin/docker-compose',

            # Add user to the Docker group
            '$SUDO usermod -aG docker `whoami`'
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
        'host': 'projectname-dev',  # Hostname or IP address of the development server
        'version': '0.0.1',  # Version of the project
        'env': 'dev',  # Environment name (e.g., dev, prod)
        'destination_dir': 'projectname',  # Directory on the server for the project
        'variables': {
            'DOMAIN': 'projectname.local'  # Additional variables specific to the development server
        }
    },
    'prod': {
        'host': 'projectname-prod',
        'version': '0.0.1',
        'env': 'prod',
        'destination_dir': 'projectname',
        'variables': {
            'DOMAIN': 'projectname.com',
            'SUDO': ''  # No sudo required for production
        }
    },
}