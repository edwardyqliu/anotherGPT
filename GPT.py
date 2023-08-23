import openai
import json
import asyncio
import ssl,certifi
from aiohttp import ClientSession, TCPConnector
import config

GPT_MODEL = "gpt-3.5-turbo"
openai.api_key = config.openai_api_key

#messages = messageHistory schemas = Function Schemas available, function_call = TYPE of response expected, model = which model to use, temperature = resp. randomness, streaming = generator/ not.
def get_json_functions(messages, schemas=None, function_call=None, model=GPT_MODEL,  temperature = 0, doStream = True):
    json_data = {"model": model, "messages": messages, "temperature":temperature,"stream":doStream}
    if schemas is not None:
        json_data.update({"functions": schemas})
    if function_call is not None:
        json_data.update({"function_call": function_call})
    return json_data

async def gpt(json_request):
            response = openai.ChatCompletion.acreate(
            **json_request
            )
            return await response
        

class GPT():
    messageHistory : list   #message history shared by all that access this instance of GPT
    stuff_lock = asyncio.Lock()
    cond = asyncio.Condition()
    def __init__(self):
        self.messageHistory = []

    #launches GPT with a message along with possible assistant/system messages too --> always a generator    
    async def launchGPT(self, message, schemas : list = None, assistant : list = None, functioncall : str = None,stream : bool = True):
        if message:
            messages = assistant + [message]
        else:
            messages = assistant
        json_data = get_json_functions(messages,schemas = schemas, function_call = functioncall, model=GPT_MODEL,doStream=stream)
        print("gpt data",json_data)
        result = await gpt(json_data)
        assistant_message = None
        fCall = ''
        fName = ''

        if not stream:
            result = result["choices"][0]["message"]
            
            if "content" in result.keys():
                assistant_message = result["content"]

            if "function_call" in result.keys():
                fName = result["function_call"]["name"]
                fCall = json.loads((result["function_call"]["arguments"]))
                yield "{FUNCTIONCALL}"
            else:
                yield "{MESSAGE}"
            if assistant_message:
                yield {"message":assistant_message} 
            if fName and fCall:
                yield {"function":(fName,fCall)}

        else:
            delay_time = 0.01 #  faster
            answer = ''
            m = ''

            start = True
            complete = False
            async for event in result:
                finished = event['choices'][0]['finish_reason']
                if finished != None:
                    complete = True

                if answer != None:
                    yield answer

                event_text = event['choices'][0]['delta'] # EVENT DELTA RESPONSE

                answer = event_text.get('content','') # RETRIEVE CONTENT
                f = event_text.get('function_call','')

                if f:
                    if start:
                        start = False
                        yield "{FUNCTIONCALL}"
                        fName = f.get('name',fName)
                        yield fName
                    
                    try:
                        fArg = f.get('arguments','')
                        fCall += fArg
                        yield fArg
                    except:
                        fCall += ''
                else:
                    if start:
                        start = False
                        yield "{MESSAGE}"
                    m += answer
                
                
                await asyncio.sleep(delay_time)
                if fName and fCall and complete:
                    yield {"function":(fName,fCall)}
                elif m and complete:
                    yield {"message":m}
    

    async def functionCall(self,Q = asyncio.Queue(), masterQ = None,**kwargs): #function
        result_gen = self.launchGPT(**{k:v for k,v in kwargs.items() if k in ["message","schemas","assistant","functioncall","stream"]})
        result = await self.unpack(result = result_gen,Q = Q,stream = kwargs["stream"],masterQ = masterQ)
        return result
         
    
    async def prompt(self,Q = asyncio.Queue(), masterQ = None,**kwargs):   
        result_gen = self.launchGPT(**{k:v for k,v in kwargs.items() if k in ["message","assistant","stream"]})
        result = await self.unpack(result = result_gen,Q = Q,stream = kwargs["stream"],masterQ = masterQ)
        return result
    
    async def unpack(self,result,Q, stream, masterQ : asyncio.Queue):
        output_q = None
        alreadyPut = False
        async for result_chunk in result:
            if output_q and not alreadyPut:
                await self.stuff_lock.acquire()
                alreadyPut = True
                await masterQ.put(output_q)     #If Q has something that requires it to be put in problemQ, try to put it ASAP. If it doesnt work, keep loading 
            if not result_chunk:
                continue
            if result_chunk == "{MESSAGE}" or result_chunk == "{FUNCTIONCALL}":
                output_q = Q                      

            else:
                try:
                    if not stream:
                        message= dict(result_chunk)["message"]
                        sentinel = {"role":"assistant","content":message}
                        await output_q.put(message)
                        return sentinel
                    if sentinel := {"role":"assistant","content":dict(result_chunk)["message"]}:
                        await output_q.put("{/MESSAGE}")
                        self.stuff_lock.release()
                        return sentinel
                except:
                    try:
                        if not stream:
                            sentinel = {"function":dict(result_chunk)["function"]}
                            await output_q.put(sentinel)
                            return sentinel
                        if sentinel:= {"function":result_chunk["function"]}:
                            await output_q.put("{/FUNCTIONCALL}")
                            self.stuff_lock.release()
                            return sentinel
                    except:
                        if stream:
                            if output_q != None:
                                await output_q.put(result_chunk)
                                await asyncio.sleep(0)
                            else:
                                print(result_chunk,end= '',flush=True)

    async def offload(self,Q : asyncio.Queue):   #these are the generators to be added to OutputListeners in Base
        lock = True
        if Q.maxsize == 0:
            lock = False
        while True:
            x = await Q.get()
            while True:
                try:
                    y = await x.get()
                    if y != "{/MESSAGE}" and y != "{/FUNCTIONCALL}":
                        yield y
                        x.task_done()
                    else:
                        yield "\n\n"
                        break
                    await asyncio.sleep(0)
                except Exception as e:
                    yield x
                    
            Q.task_done()
            if lock:
                async with self.cond:
                    await self.cond.wait()

    async def _offload(self,Q : asyncio.Queue):   #these are the generators to be added to OutputListeners in Base
        lock = True
        if Q.maxsize == 0:
            lock = False
        while True:
            x = await Q.get()
            while True:
                y = await x.get()
                if y != "{/MESSAGE}" and y != "{/FUNCTIONCALL}":
                    print(y,end ="",flush = True)
                    x.task_done()
                else:
                    print("\n")
                    break
                await asyncio.sleep(0)
            Q.task_done()
            if lock:
                async with self.cond:
                    await self.cond.wait()

if __name__ == "__main__":
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

    async def asyncmain():  #this is equiv. to handleSchema decorator
        sslcontext = ssl.create_default_context(cafile=certifi.where())
        conn = TCPConnector(ssl_context=sslcontext)
        session = ClientSession(connector=conn)
        openai.aiosession.set(session)
        gpt1 = GPT()
        STREAM = False
        output = asyncio.Queue(maxsize = 0)
        consumer = asyncio.create_task(gpt1._offload(output))
        args = [
            dict(masterQ = output, message = {"role":"user","content":"What are the French Restaurants in Hong Kong"},schemas = testSchema, assistant = gpt1.messageHistory, functioncall = "none",stream = STREAM),
            dict(masterQ = output, message = {"role":"user","content":"What killed the dinosaurs"},schemas = testSchema, assistant = gpt1.messageHistory, functioncall = {"name":"enter"},stream = STREAM),
            dict(masterQ = output, message = {"role":"user","content":"Who painted the Mona Lisa"},schemas = testSchema, assistant = gpt1.messageHistory, functioncall = "auto",stream = STREAM),
        ]


        result = await asyncio.gather(*[
            asyncio.create_task(gpt1.functionCall(**args[0])),
            asyncio.create_task(gpt1.prompt(**args[1])),
            asyncio.create_task(gpt1.prompt(**args[2])),
        ])
        consumer.cancel()   #<== always cancel consumer after outputQ closed aka this is the listener
        await openai.aiosession.get().close()
        print(result)


    gpt1 = GPT()
    asyncio.run(asyncmain())
