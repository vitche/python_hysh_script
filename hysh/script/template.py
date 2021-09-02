import os
import tempfile


class ShellTemplate:

    def __init__(self, template):
        self.template = template

    def process(self, arguments):
        result = self.template
        for key in arguments:
            result = result.replace("{" + key + "}", arguments[key])
        return result

    def save(self, arguments):
        result = self.process(arguments)

        file = tempfile.NamedTemporaryFile(delete=False)
        file.write(result)
        file.close()

        return file.name


class HyperShellTemplate(ShellTemplate):

    def __init__(self, template):
        super().__init__(template)

    def process(self, arguments, cluster_definition):
        result = super().process(arguments)

        file = tempfile.NamedTemporaryFile(delete=False)
        file.write(result.encode())
        file.close()

        command = f"hysh ${cluster_definition} ${file.name}"
        return os.system(command)


class TCPPortRange:

    def __init__(self, start):
        self.start = start

    def next(self):
        result = self.start
        self.start = self.start + 1
        return str(result)
