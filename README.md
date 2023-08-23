# anotherGPT

## Motivation
To create a **fast, flexible, semi-modular** framework to write customized GPT apps.

## Features

**Human-In-The-Loop**: use asyncio event loop for user interaction with gpt in syncronous and (untested) asyncronous tasks

**Memory (Stack/Cache)**: to show the current state of app to user and maintain consistency when GPT is runnning concurrently

**Decorators/Wrappers for handling GPT's function calls**: Eg: try first then ask user/ Ask user then do... 

**Stream/Not Stream GPT output** 

## Demo

https://github.com/edwardyqliu/anotherGPT/assets/114708188/e46fdca3-0d25-4490-a323-213b21bc922b



This is a travel agent demo. After GPT chooses to enter the travel agent process, it chooses (or asks) whether the user is asking for guides or attractions. If guides, it shows it directly in the database. If attractions, it asks the user for permission first, then creates a classifier (and adds it to the stack) and shows the list of attractions there.

## TODO
Better Streaming, Better schemas, Caching objects and function calls

# Enjoy! 🎈
