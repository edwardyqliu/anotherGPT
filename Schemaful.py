from functools import wraps
from GPT import GPT
import inspect
import asyncio
import json
class Schemaful():
    nonGPTContext : any
    gpt : GPT
    problemQ : asyncio.Queue
    userQ: asyncio.Queue
    outputQ : asyncio.Queue

    STREAM : bool
    LIMIT : int

    def __init__(self,llm, P_q ,U_q, O_q, stream = True, retrylimit = 2,timeout = 100.0):
        self.gpt = llm
        self.problemQ = P_q
        self.userQ = U_q
        self.outputQ = O_q
        self.STREAM = stream
        self.LIMIT = retrylimit 
        self.TIMEOUT = timeout

        
    def getFunctionSchemas(self) -> []:
        raise NotImplementedError
    
    def handleSchema(func):
            @wraps(func)
            async def wrapper(self,*args,**kwargs):
                assert isinstance(self,Schemaful)
                asst = []
                try:
                    if not inspect.iscoroutinefunction(func):
                        result = func(self,*args,**kwargs)
                    else:
                        result = await func(self,*args,**kwargs)
                    return result
                
                except Exception as e:
                    print("init_error",e)
                    schema = getattr(self,(str(func.__name__)+"Schema"))   #get funcSchema (list of possible Schemas) if func
                    print(schema)
                    async def recurs(count):
                        if count > self.LIMIT:
                            raise asyncio.CancelledError
                        funct,functParam,functMsg = None,None,None
                        if schema:
                            if not (funct or functParam or functMsg):
                                message = {"role":"system",
                                                "content":"Complete the function and help the user using the function calls \n"}
                                result = await self.gpt.functionCall(
                                    message = message, 
                                    masterQ = self.outputQ,
                                    schemas = schema,
                                    assistant = self.gpt.messageHistory + asst,
                                    functioncall = "auto",  #TODO Change
                                    stream = self.STREAM
                                    )
                                
                                asst.append(message)                                
                                (funct,functParam),functMsg = result.get("function",(None,None)),result

                                f = result.get("function",(None,None))
                                msg = result 
                                (funct,functParam) = f
                                if functParam and type(functParam) != dict:
                                        functParam = json.loads(functParam)

                                if not functParam and not funct:
                                    functMsg = msg
                                else:
                                    functMsg = None

                            if funct and functParam:  #function call implies execution, upon fail ask for user responses
                                funct = getattr(self,"_"+str(funct))

                                asst.append(message)
                                try:
                                    if inspect.iscoroutine(funct):
                                        result = await funct(**functParam)
                                    else:
                                        result = funct(**functParam)
                                    return result
                                
                                except Exception as e:
                                    print("error async",e)
                                    pass

                            if not functMsg:
                                message = {"role":"system",
                                            "content":f"""Your Previous Execution failed! Given the following schemas {getattr(self,(str(func.__name__)+"Schema"))}, please ask the user for more information\n"""}
                                functMsg = await self.gpt.prompt(
                                    message = message, 
                                    masterQ = self.outputQ,
                                    schemas = schema,
                                    assistant = self.gpt.messageHistory + asst,
                                    functioncall = "auto",  #TODO Change
                                    stream = self.STREAM
                                    )
                                asst.append(message)
                            
                            if functMsg:  # waited past all queues AND theres a function message 
                                print("Back from the dead")
                                asst.append(functMsg)
                                try:
                                    response = await asyncio.wait_for(self.userQ.get(),timeout = self.TIMEOUT)
                                except Exception as e:
                                    print(repr(e))
                                    raise asyncio.CancelledError
                                asst.append({"role":"user","content": response})                                
                                functMsg = None
                            
                        print(funct,functParam,functMsg,response,count)
                        await recurs(count + 1)
                await recurs(0)
            return wrapper
    
    def matchCommand(self, query : str):
        raise NotImplementedError