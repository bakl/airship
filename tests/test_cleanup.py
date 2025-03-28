#!/usr/bin/env python3

from deploy import docker_cleanup_old_versions, mes, err, deb
import subprocess
import unittest

# Minimal config emulation for tests
class TestConfig:
    def __init__(self):
        self.destination_dir = "/tmp/test"
        
# Emulate ssh function for local execution
def test_ssh(server, command):
    try:
        subprocess.run(command, shell=True, check=True)
    except subprocess.CalledProcessError as e:
        print(f"Command execution error: {e}")

# Replace real ssh function with test one
import deploy
deploy.ssh = test_ssh

def get_image_tags(image_name):
    """Get list of tags for specified image"""
    cmd = f"docker images '{image_name}' --format '{{{{.Tag}}}}'"
    output = subprocess.check_output(cmd, shell=True).decode().strip()
    return sorted([tag for tag in output.split('\n') if tag], reverse=True)

def create_test_images():
    """Create test Docker images for cleanup function testing"""
    print("\n=== Creating test images ===")
    
    # Create simple Dockerfile
    with open("Dockerfile.test", "w") as f:
        f.write("FROM alpine:latest\nCMD [\"echo\", \"test\"]")
    
    # List of versions and tags to create
    versions = ["1.0.0", "1.0.1", "1.0.2"]
    
    for version in versions:
        # Create regular version
        cmd = f"docker build -t localhost:5000/test-app:{version} -f Dockerfile.test ."
        subprocess.run(cmd, shell=True, check=True)
        
        # Create prod version
        cmd = f"docker build -t localhost:5000/test-app:{version}-prod -f Dockerfile.test ."
        subprocess.run(cmd, shell=True, check=True)
    
    # Remove temporary Dockerfile
    subprocess.run("rm Dockerfile.test", shell=True)
    
    print("Test images created successfully")

def cleanup_test_images():
    """Remove all test images"""
    try:
        # Get list of all test-app images
        cmd = "docker images 'localhost:5000/test-app' -q"
        images = subprocess.check_output(cmd, shell=True).decode().strip().split('\n')
        
        # Remove each image
        for image_id in images:
            if image_id:
                subprocess.run(f"docker rmi -f {image_id}", shell=True, check=True)
    except Exception as e:
        print(f"Error during image cleanup: {e}")

class TestDockerCleanup(unittest.TestCase):
    def setUp(self):
        """Setup before each test"""
        # Clean up old images if any remain
        cleanup_test_images()
        # Create new test images
        create_test_images()
        
        # Base test data
        self.server = {
            'host': 'localhost',
            'user': '',
            'port': ''
        }
        
        self.variables = {
            'VERSION': '1.0.0',
            'ENV': 'test',
            'BUILD_TYPE': 'prod'
        }

    def tearDown(self):
        """Cleanup after each test"""
        cleanup_test_images()

    def test_basic_cleanup(self):
        """Test basic cleanup - keep 2 latest versions"""
        # Check initial state
        initial_tags = get_image_tags('localhost:5000/test-app')
        self.assertEqual(len(initial_tags), 6, "Should be 6 tags before cleanup")
        
        # Container configuration
        container = {
            'name': 'test-app:1.0.0',
            'registry': 'localhost:5000',
            'cleanup_old': True,
            'keep_versions': 2
        }
        
        # Run cleanup
        docker_cleanup_old_versions(self.server, self.variables, container)
        
        # Check result
        remaining_tags = get_image_tags('localhost:5000/test-app')
        self.assertEqual(len(remaining_tags), 2, "Should remain 2 tags")
        self.assertIn('1.0.2', remaining_tags, "Tag 1.0.2 should remain")
        self.assertIn('1.0.2-prod', remaining_tags, "Tag 1.0.2-prod should remain")

    def test_prod_cleanup(self):
        """Test prod versions cleanup"""
        # Check initial state
        initial_tags = get_image_tags('localhost:5000/test-app')
        self.assertEqual(len(initial_tags), 6, "Should be 6 tags before cleanup")
        
        # Container configuration
        container = {
            'name': 'test-app:1.0.0-prod',
            'registry': 'localhost:5000',
            'cleanup_old': True,
            'keep_versions': 2,
            'cleanup_pattern': '*-prod'
        }
        
        # Run cleanup
        docker_cleanup_old_versions(self.server, self.variables, container)
        
        # Check result
        remaining_tags = get_image_tags('localhost:5000/test-app')
        prod_tags = [tag for tag in remaining_tags if tag.endswith('-prod')]
        non_prod_tags = [tag for tag in remaining_tags if not tag.endswith('-prod')]
        
        self.assertEqual(len(prod_tags), 2, "Should remain 2 prod tags")
        self.assertEqual(len(non_prod_tags), 3, "Should remain all non-prod tags")
        self.assertIn('1.0.2-prod', prod_tags, "Tag 1.0.2-prod should remain")
        self.assertIn('1.0.1-prod', prod_tags, "Tag 1.0.1-prod should remain")

    def test_cleanup_disabled(self):
        """Test with cleanup disabled"""
        # Check initial state
        initial_tags = get_image_tags('localhost:5000/test-app')
        self.assertEqual(len(initial_tags), 6, "Should be 6 tags before cleanup")
        
        # Container configuration
        container = {
            'name': 'test-app:1.0.0',
            'registry': 'localhost:5000',
            'cleanup_old': False
        }
        
        # Run cleanup
        docker_cleanup_old_versions(self.server, self.variables, container)
        
        # Check result
        remaining_tags = get_image_tags('localhost:5000/test-app')
        self.assertEqual(len(remaining_tags), 6, "Should remain all 6 tags")
        self.assertEqual(set(remaining_tags), set(initial_tags), "Tag list should not change")

if __name__ == '__main__':
    unittest.main(verbosity=2) 