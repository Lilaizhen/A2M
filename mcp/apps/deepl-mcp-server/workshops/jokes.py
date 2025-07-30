# Warning - I have not tried this out yet, so there may be 🐞🐞🐞

### Setup commands:
#
# uv venv
# source .venv/bin/activate
# uv init
# uv add fastmcp
# uv add requests
# uv add "mcp[cli]" (if you want to debug with the MCP Inspector)

import os
import requests
from fastmcp import FastMCP

API_BASE_URL = 'https://official-joke-api.appspot.com'
JOKE_TYPES = ["general", "knock-knock", "programming", "dad"]
CONSISTENT_JOKE = "What's brown and sticky?\nA stick! Ha ha ha ha"

mcp = FastMCP("jokes in Python")

### Tools!

@mcp.tool
def get_consistent_joke() -> str:
  '''Tell the same joke, every single time. Be consistent.'''
  return CONSISTENT_JOKE

@mcp.tool
def get_joke() -> str:
  "Get a random joke"
  response = requests.get(API_BASE_URL + '/random_joke')
  json = response.json()
  return extract_joke(json)
  
@mcp.tool
def get_joke_by_id(id: int) -> str:
  "Get a joke with a specific id"
  response = requests.get(f"{API_BASE_URL}/jokes/{id}")
  json = response.json()
  return extract_joke(json)

@mcp.tool
def get_joke_by_type(joke_type: str) -> str:
  """
  Get a joke of a specific type.
  The type can be "general", "knock-knock", "programming", or "dad".
  """
  response = requests.get(f"{API_BASE_URL}/{joke_type}/random")
  json = response.json()
  return extract_joke(json[0])


### Helper function
def extract_joke(json: dict) -> str:
  return f"{json['setup']}\n{json['punchline']}"
  

if __name__ == "__main__":
  mcp.run()