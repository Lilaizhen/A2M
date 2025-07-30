// Thanks to https://github.com/15Dkatz/official_joke_api !

/* To set up this project and install dependencies: 
npm init -y
npm install @modelcontextprotocol/sdk zod axios
*/

// Do basic setup. We'll start our server off with no resources or tools. We'll add those later.

const { McpServer } = require("@modelcontextprotocol/sdk/server/mcp.js");
const { StdioServerTransport } = require("@modelcontextprotocol/sdk/server/stdio.js");
const z = require("zod");
const axios = require("axios");

const API_BASE_URL = 'https://official-joke-api.appspot.com/';
const jokeTypes = ["general", "knock-knock", "programming", "dad"];
const consistentJoke = "What's brown and sticky?\nA stick! Ha ha ha ha";

const server = new McpServer({
  name: "jokes",
  version: "1.0.0",
  capabilities: {
    resources: {},
    tools: {}
  },
});

// Add tools to our server

// First, add a tool that simply returns a constant
server.tool(
  'get-consistent-joke',
  'Tell the same joke, every single time',
  async () => ({content: [{type: "text", text: consistentJoke }]})
);

// Next, slightly more elaborate - a tool that calls the joke API
server.tool(
  'get-joke',
  'Get a random joke',
  randomJoke
);

// Slightly more advanced: a tool which wants to be passed an integer in a fixed range
server.tool(
  'get-joke-by-id',
  'Get a joke with a specific id',
  {
    id: z.number().int().gt(0).lt(452)
  },
  jokeByID
);

// Finally, a tool which expects one of a set of strings
server.tool(
  'get-joke-by-type',
  'Get a joke of a specific type',
  {
    jokeType: z.enum(jokeTypes)
  },
  jokeByType
);


/* These helper functions  call the Jokes API */

async function randomJoke() {
  try {
    const res = await axios.get(API_BASE_URL + '/random_joke');

    return {
      content: [
        { 
          type: "text", 
          text: `${res.data.setup}\n... wait for it...\n${res.data.punchline}` 
        }
      ]
    };
  } catch (error) {
    handleJokeFetchError(error);
  }
}

async function jokeByID({ id }) {
  try {
    const res = await axios.get(`${API_BASE_URL}/jokes/${id}`);

    return {
      content: [
        { 
          type: "text", 
          text: `${res.data.setup}\n${res.data.punchline}` 
        }
      ]
    };
  } catch (error) {
    handleJokeFetchError(error);
  }
}

async function jokeByType({ jokeType }) {
  try {
    const res = await axios.get(`${API_BASE_URL}/jokes/${jokeType}/random`);
    console.error(res);

    if (res.data?.[0]) {
      return {
        content: [
          { 
            type: "text", 
            text: `${res.data[0].setup}\n${res.data[0].punchline}` 
          }
        ]
      }
    } else {
      throw new Error('The joke API was supposed to return an array');
    }
  } catch (error) {
    handleJokeFetchError(error);
  }
}


// The client will run this to fire up our server

async function main() {
  const transport = new StdioServerTransport();
  await server.connect(transport);
  console.error("The jokes server is running on stdio, wahoo");
}

main().catch((error) => {
  console.error("The joke's on you. The server's busted! Fatal error: ", error);
  process.exit(1);
});

// FInally, a helper function to deal with errors
function handleJokeFetchError(error) {
  console.error("Error fetching joke: ", error);

  return {
    isError: true,
    content: [
      {
        type: "text",
        text: "Sorry, I failed to fetch a joke. I am... a joke." 
      }
    ]
  };
}