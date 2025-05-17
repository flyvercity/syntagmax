import logging as lg
import os
import json
from datetime import datetime

import click
from mcp.server.fastmcp import FastMCP


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
        notify_mcp(f'Using config descriptor: {self.config_descriptor}')


connector = Connector()
mcp = FastMCP('System Requirements Source')


@mcp.tool()
def get_requirement(requirement_id: str) -> str:
    '''Get a system requirement by ID.'''
    return f'Requirement {requirement_id}'


@click.command(name='mcp')
def mcp_cmd():
    lg.info('Starting MCP server')
    mcp.run()


if __name__ == '__main__':
    mcp.run()
