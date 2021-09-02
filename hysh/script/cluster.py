import os
import uuid
import json
from enum import Enum
from hysh.script.template import HyperShellTemplate, ShellTemplate


class HyperShellClusterOperationType(Enum):
    TOPOLOGY = 1
    IDENTIFIERS = 2
    SETTINGS = 3
    CONTROLLER = 4
    WORKER = 5


class HyperShellClusterOperationFormat(Enum):
    UNKNOWN = 1
    TEXT = 2
    JSON = 3


# The strategy object to process operations
class HyperShellCluster:
    identifiers = []
    settings = {}

    def __init(self, identifiers=None):
        if identifiers is None:
            identifiers = []
        self.identifiers = identifiers

    def process(self, operation):
        if HyperShellClusterOperationType.IDENTIFIERS == operation.operation_type:
            self.identifiers = operation.payload
            return operation.process(self.identifiers)
        elif HyperShellClusterOperationType.TOPOLOGY == operation.operation_type:
            return operation.process(self.settings)
        elif HyperShellClusterOperationType.SETTINGS == operation.operation_type:
            self.settings = operation.payload
        elif HyperShellClusterOperationType.CONTROLLER == operation.operation_type:
            return operation.process(self.settings)
        elif HyperShellClusterOperationType.WORKER == operation.operation_type:
            return operation.process(self.settings)


class HyperShellClusterOperation:

    def __init__(self, operation_type, payload, output_format=HyperShellClusterOperationFormat.UNKNOWN):
        self.operation_type = operation_type
        self.payload = payload
        self.output_format = output_format

    def process(self, settings):

        output_format = "stream+text"
        if HyperShellClusterOperationFormat.JSON == self.output_format:
            output_format = "stream+json"

        if isinstance(self.payload, HyperShellTemplate):
            if HyperShellClusterOperationType.CONTROLLER == self.operation_type:
                return self.payload.process(settings, settings["CONTROLLER_CLUSTER_DEFINITION"])
            elif HyperShellClusterOperationType.WORKER == self.operation_type:
                return self.payload.process(settings, settings["WORKER_CLUSTER_DEFINITION"])
        else:
            if HyperShellClusterOperationType.TOPOLOGY == self.operation_type:
                # By-default we consider that topology requests are processed
                # by the controller organization.
                # TODO: Fix otherwise
                path = settings["CONTROLLER_CLUSTER_DEFINITION"]
                command = f"hyshm ${path} \"{self.payload}\" --format ${output_format}"
                return os.system(command)
            elif HyperShellClusterOperationType.IDENTIFIERS == self.operation_type:
                return self.payload
            elif HyperShellClusterOperationType.CONTROLLER == self.operation_type:
                path = settings["CONTROLLER_CLUSTER_DEFINITION"]
                command = f"hysh ${path} \"{self.payload}\" --format ${output_format}"
                return os.system(command)
            elif HyperShellClusterOperationType.WORKER == self.operation_type:
                path = settings["WORKER_CLUSTER_DEFINITION"]
                command = f"hysh ${path} \"{self.payload}\" --format ${output_format}"
                return os.system(command)


class HyperShellClusterCLI:

    def __init__(self):
        self.cluster = HyperShellCluster()

    def generate(self, count):
        payload = []
        for i in range(count):
            payload.append(str(uuid.uuid4()))
        return self.cluster.process(HyperShellClusterOperation(HyperShellClusterOperationType.IDENTIFIERS, payload))

    def load(self, path):
        if os.path.isfile(path):
            with open(path, "r") as file:
                payload = json.load(file)
                file.close()
                return self.cluster.process(
                    HyperShellClusterOperation(HyperShellClusterOperationType.IDENTIFIERS, payload))
        return []

    @staticmethod
    def remove(path):
        os.remove(path)

    def save(self, path):
        with open(path, "w") as file:
            json.dump(self.cluster.identifiers, file)

    def save_json(self, path, installer_uri, gateway_uri):
        cluster_template = ShellTemplate("""{
          "installer": {
            "uri": "{installer.uri}"
          },
          "gateway": {
            "uri": "{gateway.uri}"
          },
          "nodes": [
{nodes}
          ]
        }""")
        node_template = ShellTemplate("""{
          "msp": {
            "identifier": "Org1MSP"
          },
          "administrator": {
            "logOn": "Admin@org1.example.com",
            "password": "adminpw"
          },
          "identifier": "node-{index}",
          "chainCode": {
            "identifier": "{identifier}"
          }
        }""")
        nodes = ""
        i = 0
        for identifier in self.cluster.identifiers:
            node = node_template.process({"index": str(i), "identifier": identifier})
            nodes += node
            if i != len(self.cluster.identifiers) - 1:
                nodes += ", "
            i = i + 1
        cluster_json = cluster_template.process({
            "installer.uri": installer_uri,
            "gateway.uri": gateway_uri,
            "nodes": nodes
        })

        with open(path, "w") as file:
            file.write(cluster_json)

    def install(self):
        results = []
        for i in self.cluster.identifiers:
            payload = f"install " \
                      f"--organization-identifier Org1MSP " \
                      f"--administrator-logon Admin@org1.example.com " \
                      f"--administrator-password adminpw " \
                      f"--chaincode-name shell-linux " \
                      f"--chaincode-identifier {i} " \
                      f"--chaincode-version 0.0.1"
            result = self.cluster.process(HyperShellClusterOperation(HyperShellClusterOperationType.TOPOLOGY, payload,
                                                                     HyperShellClusterOperationFormat.TEXT))
            # Get standard output
            result = result[0]
            # Parse JSON response
            result = json.loads(result)
            results.append(result)
        return results

    def instantiate(self):
        results = []
        for i in self.cluster.identifiers:
            payload = f"instantiate " \
                      f"--organization-identifier Org1MSP " \
                      f"--administrator-logon Admin@org1.example.com " \
                      f"--administrator-password adminpw " \
                      f"--chaincode-name {i} " \
                      f"--chaincode-version 0.0.1"
            result = self.cluster.process(HyperShellClusterOperation(HyperShellClusterOperationType.TOPOLOGY, payload,
                                                                     HyperShellClusterOperationFormat.TEXT))
            # Get standard output
            result = result[0]
            # Parse JSON response
            result = json.loads(result)
            results.append(result)
        return results

    def package(self):
        cluster_definition = self.cluster.settings["CONTROLLER_CLUSTER_DEFINITION"]
        command = f"hyshm \"${cluster_definition}\" package"
        return os.system(command)

    def c(self, payload):
        return self.cluster.process(HyperShellClusterOperation(HyperShellClusterOperationType.CONTROLLER, payload,
                                                               HyperShellClusterOperationFormat.TEXT))

    def cj(self, payload):
        result = self.cluster.process(HyperShellClusterOperation(HyperShellClusterOperationType.CONTROLLER, payload,
                                                                 HyperShellClusterOperationFormat.JSON))
        # Get standard output
        result = result[0]
        # Remove comma from the JSON stream
        result = result.rstrip(",")
        # Parse JSON response
        result = json.loads(result)
        # Extract HySh transaction output
        result = result["output"]
        # Parse transaction output
        result = json.loads(result)
        return result

    def ct(self, payload):
        template = HyperShellTemplate(payload)
        return self.cluster.process(HyperShellClusterOperation(HyperShellClusterOperationType.CONTROLLER, template,
                                                               HyperShellClusterOperationFormat.TEXT))

    def s(self, payload):
        return self.cluster.process(HyperShellClusterOperation(HyperShellClusterOperationType.SETTINGS, payload,
                                                               HyperShellClusterOperationFormat.TEXT))

    def w(self, payload):
        return self.cluster.process(HyperShellClusterOperation(HyperShellClusterOperationType.WORKER, payload,
                                                               HyperShellClusterOperationFormat.TEXT))

    def wt(self, payload):
        template = HyperShellTemplate(payload)
        return self.cluster.process(HyperShellClusterOperation(HyperShellClusterOperationType.WORKER, template,
                                                               HyperShellClusterOperationFormat.TEXT))
