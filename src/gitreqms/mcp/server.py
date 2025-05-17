import os
import json
from datetime import datetime
from typing import Any, Coroutine

import click
from mcp.server.fastmcp import FastMCP
from mcp.types import Resource as MCPResource


def notify_mcp(message: str):
    'Sends an MCP notification to the client via STDIO.'

    notification = {
        'jsonrpc': '2.0',
        'method': 'mcp.server.notification',
        'params': {
            'type': 'log',
            'data': {
                'message': message,
                'level': 'info',
                'timestamp': datetime.now().isoformat() + 'Z'
            }
        }
    }

    json_str = json.dumps(notification)
    print(json_str, flush=True)


class Connector():
    def load(self):
        self.config_descriptor = os.getenv('GITREQMS_MCP_DESCRIPTOR')
        notify_mcp(f'Listing resources from {self.config_descriptor}')


class Server(FastMCP):
    def __init__(self, connector: Connector):
        super().__init__('Software Requirements Source')
        self.connector = connector

    def list_resources(self) -> Coroutine[Any, Any, list[MCPResource]]:
        self.connector.load()
        return super().list_resources()


connector = Connector()
mcp = Server(connector)


@mcp.resource('requirement://{rid}')
def get_requirement(rid: str) -> str:
    notify_mcp(f'Getting requirement {rid}')
    return 'test'


@click.command(name='mcp')
def mcp_cmd():
    mcp.run()
