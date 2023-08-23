from GPT import GPT
from Schemaful import Schemaful
from MemHandler import MemHandler
import asyncio
import openai
import ssl
import certifi
from aiohttp import ClientSession, TCPConnector
'''
Basic Client defined w/ most reasonable dependent methods.
Wraps all compnents into one, declare dependent methods and offer connection endpoints to Server
'''
class Base():   #wraps all components into one and connects to client
    currobj : any
    gpt: GPT
    STREAM : bool
    LIMIT : int
    problemQ: asyncio.Queue    #Queue for asking User
    outputQ: asyncio.Queue     #Queue for relaying output to user
    userQ: asyncio.Queue       #Queue for user to respond
    memhandler: MemHandler

    def __init__(self,stream):
        self.gpt = GPT()
        self.problemQ = asyncio.Queue(maxsize = 1)
        self.outputQ = asyncio.Queue()
        self.userQ = asyncio.Queue(maxsize = 1)
        self.LIMIT = 2
        self.STREAM = stream
        self.timeout = 100.0
        
        self.config = dict(llm = self.gpt,     
                      P_q = self.problemQ,    
                      U_q = self.userQ,        
                      O_q = self.outputQ,      
                      stream = self.STREAM,   
                      retrylimit = self.LIMIT, 
                      timeout = self.timeout
                      )
        '''
        Schemaful Init Params: \n
            llm = your Large Language Model Interpreter, stores chat history\n
            P_q = (Problem Q) for GPT to question user (default size = 1) \n
            U_q = (User Q) for user to reply to \n
            O_q = (Output Q) for GPT to update user (default size = 1) \n
            stream = to stream results or not (default = False) \n
            retrylimit = to retry event loop X times (default = 2) \n
            timeout = time to wait for user to respond before closing response (default = 100.0s) \n
        '''
    '''
    Base Methods
    '''
    def getCurrentObject(self):
        self.currobj = self.memhandler.currobj
        assert(isinstance(self.currobj,Schemaful))
        return self.currobj

    '''
    Listener Methods
    '''
    async def listener(self):
        await asyncio.sleep(1)
        print(self.outputQ,self.problemQ,self.userQ)
        async for item in self.gpt.offload(self.outputQ):
            print(item, end = "",flush = True)
            if item != "{BREAK}":   #sentinel
                    yield str(item) + '\BR\n'

            else:
                break
                
        async for item in self.gpt.offload(self.problemQ):
            print(item,end = "",flush = True)
            if item != "{BREAK}":
                yield str(item) + '\BR\n'
            else:
                break
        
        print("Listener Closed")

async def asyncmain():  #this is equiv. to handleSchema decorator
        sslcontext = ssl.create_default_context(cafile=certifi.where())
        conn = TCPConnector(ssl_context=sslcontext)
        session = ClientSession(connector=conn)
        openai.aiosession.set(session)
        testSchema = [{
            "name":"enter",
            "description": "Search Database for answer, getting the appropriate data and tool.",
            "parameters":{
                "type":"object",
                "properties":{
                    "tool":{
                    "type":"string",
                    "description": "The tool as recommended by the database.",
                    "enum": ["SEARCH","DELETE","QUERY","NEWS"],
                    },
                    "section":{
                        "type":"string",
                        "description": "The section in which the data most likely resides.",
                        "enum":["Dinosaurs","Chemistry","Philosophy"]
                    },
                },
            },
            "required":["tool","section"],
            }]
        
        async def simulateCondRelease(time : int):
            await asyncio.sleep(time)
            print("released")
            async with client.gpt.cond:
                client.gpt.cond.notify()
                print("done")
        
        client = Base()
        STREAM = True
        args = [
            dict(masterQ = client.problemQ, message = {"role":"user","content":"What killed the dinosaurs"},schemas = testSchema, assistant = client.gpt.messageHistory, functioncall = {"name":"enter"},stream = STREAM),
            dict(masterQ = client.problemQ, message = {"role":"user","content":"Who painted the Mona Lisa"},schemas = testSchema, assistant = client.gpt.messageHistory, functioncall = "auto",stream = STREAM),
            dict(masterQ = client.problemQ, message = {"role":"user","content":"Who shot Alexander Hamilton"},schemas = testSchema, assistant = client.gpt.messageHistory, functioncall = "none",stream = STREAM)
        ]
        
        result = await asyncio.gather(*[
            asyncio.create_task(client.gpt.functionCall(**args[0])),
            asyncio.create_task(client.gpt.prompt(**args[1])),
            asyncio.create_task(client.gpt.prompt(**args[2]))
        ])

        ''' result = [
            await client.gpt.functionCall(**args[0]),
            await client.gpt.functionCall(**args[1]),
            await client.gpt.functionCall(**args[2]),
            asyncio.create_task(simulateCondRelease(5)),
            asyncio.create_task(simulateCondRelease(10)),
            asyncio.create_task(simulateCondRelease(15)),
        ]'''
        await openai.aiosession.get().close()
        return result

if __name__ == "__main__":
    print(asyncio.run(asyncmain()))
    print("\ntest complete")
