from fastapi import FastAPI
from fastapi.responses import StreamingResponse
import uvicorn 
from pydantic import BaseModel
import json
import asyncio 
from TravelAgent import TravelAgent
import ssl
import certifi
import openai
from aiohttp import TCPConnector, ClientSession
import pandas as pd

app = FastAPI()

class UserInput(BaseModel):
    u_text : str

    def get(self):
        return dict(u_text = self.u_text)

class Server():
    room =  TravelAgent(stream = True)  #<== swap this with whichever Agent you want
    serverLock = asyncio.Lock()
    
        

server = Server()
@app.post("/GPT")
async def run(uinput : UserInput):
    async with server.serverLock:
        sslcontext = ssl.create_default_context(cafile=certifi.where())
        conn = TCPConnector(ssl_context=sslcontext)
        session = ClientSession(connector=conn)
        openai.aiosession.set(session)
        
        u_text = uinput.get().get("u_text","")
        room = server.room   

        #current Object
        currObjList = [currObj := room.getCurrentObject()]
        if not isinstance(currObj,type(room.memhandler)):
            room.prevObj = currObj
            currObjList.append(room.memhandler)
        
        else:
            try:
                currObjList.append(room.prevObj)
            except:
                pass
        #execution conditional upon user query input
        if not u_text:
            return
        
        #clear context
        room.gpt.messageHistory = room.base.copy()     #room.base or room.base.copy changes whether chat history is saved from last API call
        print("cleared")
        command = None
        if u_text.startswith("+") or u_text.startswith("-"):    #command definition
            command = [x for x in map(lambda foo: foo.matchCommand(u_text), currObjList) if x]   #should only be one
            return command
        
        else:
            room.gpt.messageHistory.append({"role":"user","content":u_text})    #if not command add to message history
            async def execute():
                schema2D = [y.getFunctionSchemas() for y in  currObjList]   #every obj here has a Schema
                schema_arr, schema_index = [],[]
                for j in enumerate(schema2D):
                    index,arr = j
                    if arr:
                        for k in arr:
                            schema_index.append(index)
                            schema_arr.append(k)

                msg = {"role":"system",
                        "content":"Based on user's helpful input and your previous errors, try to complete this function. If you aren't sure, don't guess a function instead prompt the user for more information. \n"}

                if schema_arr: 
                    result = await room.gpt.functionCall(
                                                message = msg, 
                                                masterQ = room.outputQ,
                                                schemas = schema_arr,
                                                assistant = room.gpt.messageHistory,
                                                functioncall = "auto", 
                                                stream = room.STREAM
                                                )
                else:
                    result = await room.gpt.prompt(
                                                message = msg, 
                                                masterQ = room.outputQ,
                                                assistant = room.gpt.messageHistory,
                                                stream = room.STREAM
                                                )
                #step 2 execute & succeed / timeout / fail
                f = dict(result).get("function",(None,None))
                msg = result 
                (funct,functParam) = f
                if functParam and type(functParam) != dict:
                        functParam = json.loads(functParam)
                print("funct",funct)
                print("functParam",functParam)

                if funct:
                    for index,schema in enumerate(schema_arr):
                        if schema["name"] == funct:     #TODO Inheritance not implemented
                            funct = getattr(currObjList[schema_index[index]],funct)     #turn function alive
                            break
                    try:
                        await funct(**functParam)   #<== expect All functions called to be handled by some form of schema and schema handler
                    except Exception as e:
                        print("fail",e)
                else:
                    room.gpt.messageHistory.append(msg)
                    pass

                print("Done")
                await openai.aiosession.get().close()
                room.outputQ.put_nowait("{BREAK}")
                await room.problemQ.put("{BREAK}")
                task.done()
                return

            task = asyncio.create_task(execute())
            #step 3 pickle and save Base to server
            return StreamingResponse(room.listener(), media_type='text/event-stream') 

@app.get("/getCurrentObject")
def getCurrentObject():
    room = server.room
    result = room.getCurrentObject().nonGPTContext
    print(room.currobj)
    print(result)
    if type(result) == pd.DataFrame:
        result = result.to_dict()
    return result

@app.post("/reply") #reply to userQ
async def reply(uinput : UserInput):
    async with server.serverLock:
        u_text = uinput.get().get("u_text","")
        room = server.room
        #step 2 execute (trivial)
        try:
            room.userQ.put_nowait(u_text)  #<== put here to whatever context is in need
            return StreamingResponse(room.listener(),media_type = 'text/event-stream')
        except Exception as e:
            print("reply error",e)
            return "One Response at a time"
        #step 3 ~~~ Nothing


if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8000,log_level = "debug")
