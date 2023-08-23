from Schemaful import Schemaful
from collections import OrderedDict
from GPT import GPT
import asyncio

def list_rindex(li, x):
            for i in reversed(range(len(li))):
                if li[i] == x:
                    return i
            raise ValueError("{} is not in list".format(x))

class Cache:
    def __init__(self, capacity):
        self.capacity = capacity
        self.values = OrderedDict()
        #cache always has root available

    def get(self, key: int):
        if key not in self.keys():
            return None
        else:
            self.values[key] = self.values.pop(key)
            return self.values[key]

    def put(self, key: int, value, stack = []):    
        if key in self.values:
            self.values.pop(key)
        
        #weakly pop least recently used objects, unless they are in the current stack
        excess =  len(self.values) - self.capacity 
        self.values[key] = value
        copy = self.values.copy()
        for key_iter in self.values.keys():  #TODO Might be a problem here
            if excess < 0:
                break
            elif key_iter not in stack:
                copy.move_to_end(key_iter,last = True)
                copy.popitem(last = True)
                excess -= 1
        self.values = copy    
    def keys(self):
        return self.values.keys()
    
class Stack:
    context: list
    pointer: int
    def __init__(self):
        self.pointer = -1
        self.context = []
    
    '''Gets object in stack if exists, else returns root node with object'''
    def get(self,key : int):
        if key <0:
            return None
        try:
            self.pointer = list_rindex(self.context,key)
        except:
            self.pointer = 0 
            self.put(key)
        return self.context[self.pointer]
    
    def put(self, key : int):
        self.context = self.context[ : self.pointer + 1]
        self.context.append(key)
        self.pointer = len(self.context) - 1    #to top of stack

    def prev(self):
        if self.pointer > 0:
            self.pointer -= 1
        return self.context[self.pointer]
    
    def next(self):
        if self.pointer < len(self.context) - 1:
            self.pointer += 1
        return self.context[self.pointer]
    
    def curr(self):
        return self.context[self.pointer]

class MemHandler(Schemaful):
    cache: Cache
    stack: Stack
    objcount: int

    def __init__(self,cachelimit : int = 10, *args,**kwargs):
        super().__init__(*args,**kwargs)
        self.cache = Cache(capacity = cachelimit)
        self.stack = Stack()
        self.objcount = 0
        self.currobj = self

    def _create(self):
        key = self.objcount
        self.objcount += 1
        return key
    
    def put(self,obj,key :int = None):
        if key == None: #if no key, _create item key
            key = self._create()
        #appends to stack
        self.stack.put(key)
        #update cache
        self.cache.put(key, obj, self.stack.context)
        self.currobj = self.cache.get(key)
        return key
    
    def get(self,key : int):
        if key not in self.cache.keys():
            raise ValueError
        
        self.stack.get(key)
        item = self.cache.get(key)
        self.currobj = item
        return self.currobj 

    def backwards(self):
        self.currobj = self.cache.get(self.stack.prev())
        return self.currobj
    

    def forwards(self):
        self.currobj = self.cache.get(self.stack.next())
        return self.currobj
    
    def current(self):
        self.currobj - self.cache.get(self.stack.curr())
        return self.currobj

    '''
    Use with care! 
    Delete key from stack, useful for concurrency when LOCAL STACK MEMORY IS LOCALLY MAINTAINED
    '''
    def delete(self,key : int):
        if key in self.stack.context:
            self.stack.context.remove(key)

    def showStack(self) -> list:
        x = sorted([(x,str(self.cache.values.get(x))) for x in self.cache.keys() if x in self.stack.context])
        self.nonGPTContext = x
        self.currobj = self
        return x
    
    def showCache(self) -> list:
        self.nonGPTContext = [(id,str(item)) for (id,item) in self.cache.values.items()]
        self.currobj = self

    @Schemaful.handleSchema #<== this one accessed by event loop
    def getByGPT(self,index : int):
        assert index != None
        self.get(index)
    
    def _getByGPT(self,index : int):    #<== this one operated on
        assert index != None
        self.get(index)

    def getFunctionSchemas(self) -> list:
        self.getByGPTSchema = [{
        "name":"getByGPT",
        "description": f"Gets user requested item from list of items by index, based on this list {self.showStack()} ",
        "parameters":{
            "type":"object",
            "properties":{
                "index":{
                    "type":"integer",
                    "description": "The index of the item in the list",
                }
            }
        },
        "required":["index"]
        }]
        return self.getByGPTSchema
    
    def matchCommand(self,query : str):
        if not query.strip().startswith("+"):
            return None
        
        match query.strip().lower():            
            case "+backwards" if len(self.cache.values) > 0 and len(self.stack.context) > 0:
                #move backwards in stack
                self.backwards()
        
            case "+forwards" if len(self.cache.values) > 0 and len(self.stack.context) > 0:
                #move forwards in stack
                self.forwards()
        
            case "+showstack":
                #enumerate stack
                self.showStack()
        
            case "+showcache":
                #enumerate cache
                self.showCache()
            
            case query_f if "+get" in query_f and len(self.cache.values) > 0 and len(self.stack.context) > 0:
                #gets from cache. Clips stack to that item or creates new singleton stack
                num = int(query_f.split("+get")[1].strip())
                self.get(num)
            
            case _ if len(self.cache.values) > 0 and len(self.stack.context) > 0:
                return "Here are the possible memory level commands:\n \
                        1. +backwards \n \
                        2. +forwards \n \
                        3. +showStack \n \
                        4. +showcache \n \
                        5. +get N for N in Cache \n \
                        To view object commands, use -help \n \
                        Cheers! "
    
#TEST
if __name__ == "__main__":  #Try in Debug
    memTest = MemHandler(cachelimit = 10, llm = GPT, P_q = asyncio.Queue(maxsize=1),U_q = asyncio.Queue(maxsize = 1),O_q = asyncio.Queue())
    memTest.put("A")
    memTest.put("B")
    memTest.put("C")
    memTest.put("D")
    memTest.put("E")
    memTest.put("F")

    print("Test Complete")
