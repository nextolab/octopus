import logging
import sys
import shutil
import subprocess
import time

import docker
from docker.models.networks import Network
from docker.models.containers import Container as DockerContainer


class Container:
    def __init__(self, project: str, ip_address: str, exposed_ports: dict[str, str]):
        self.project = project
        self.ip_address = ip_address
        self.exposed_ports = exposed_ports


class Octopus:
    def __init__(
        self,
        client: docker.DockerClient,
        network_name: str,
        loop_back_domain: str
    ) -> None:
        self.client = client
        self.loop_back_domain = loop_back_domain
        self.network_name = network_name

        self.network = self.catch_network()
        self.containers: dict[str, Container] = {}

    def catch_network(self) -> Network:
        try:
            network = self.client.networks.get(self.network_name)
            logging.info(f"Network {self.network_name} was founded")
        except docker.errors.NotFound:
            network = self.client.networks.create(self.network_name)
            logging.info(f"Network {self.network_name} was created")

        return network

    def grab(self) -> None:
        while True:
            has_new_containers = False
            founded_containers: list[str] = []

            for container in self.client.containers.list():
                founded_containers.append(container.name)
                has_new_containers = self.add_container(container) or has_new_containers

            lost_containers: list[str] = [name for name in self.containers if name not in founded_containers]

            for name in lost_containers:
                del self.containers[name]
                logging.info(f"[-] {name}")

            if has_new_containers or lost_containers:
                self.reload_hosts_config()
                self.reload_nginx_config()

                subprocess.run(['nginx', '-s', 'reload'])
                logging.info(f"Configs was applied")

            time.sleep(5)

    def add_container(self, container: DockerContainer) -> bool:
        if not self.connect_container(container):
            return False

        if container.name not in self.containers:
            self.containers[container.name] = Container(
                project=container.attrs.get('Config', {}).get('Labels', {}).get('com.docker.compose.project', ''),
                ip_address=container.attrs['NetworkSettings']['Networks'][self.network_name]['IPAddress'],
                exposed_ports=container.attrs['Config']['ExposedPorts']
            )

            logging.info(f"[+] {container.name}")
            return True

        return False

    def connect_container(self, container: DockerContainer) -> bool:
        if self.network_name not in container.attrs['NetworkSettings']['Networks']:
            try:
                self.network.connect(container.name)
                container.reload()
            except docker.errors.APIError as e:
                logging.error(f"Can't add container {container.name} to the network: {e}")
                return False

            return True

    def reload_hosts_config(self) -> None:
        config = ""

        with open('/etc/hosts', 'r') as file:
            current_config = file.readlines()

        for line in current_config:
            if '# OCTOPUS' in line:
                break
            config += line

        config += "# OCTOPUS\n"

        for name, container in self.containers.items():
            config += f"{container.ip_address}    {name}\n"

        with open('/etc/hosts', 'w') as file:
            file.write(config)

    def reload_nginx_config(self) -> None:
        config = "map $host $proxy {\n"

        for name, container in self.containers.items():
            if '80/tcp' in container.exposed_ports or '443/tcp' in container.exposed_ports:
                domain = container.project if container.project else name
                config += f"    {domain}.{self.loop_back_domain} {container.ip_address};\n"

        config += "}\n\n"

        config += ("server {\n"
                   "    listen 80;\n"
                   f"    server_name *.{self.loop_back_domain};\n\n"
                   "    location / {\n        proxy_pass http://$proxy;\n    }\n"
                   "}")

        with open('/etc/nginx/conf.d/proxy.conf', 'w') as file:
            file.write(config)


if __name__ == "__main__":
    logging.basicConfig(stream=sys.stdout, level=logging.INFO, format='OCTOPUS: %(message)s')
    shutil.copyfile('/app/key.pub', '/root/.ssh/authorized_keys')

    octopus = Octopus(docker.from_env(), 'nextolab-octopus', 'nextolab.com')
    octopus.grab()
