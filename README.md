# Activity Intelligence Framework (ACTINT) for multi-target tracking

# Setup

We use conda for environment management. To set up the environment, run the following command in the terminal, run the following from the actint directory (where this README is located):

```bash
conda create -n actint python=3.12 -y 
conda activate actint
pip install -r requirements.txt
pip install -e .
```

to run the muli-agent system, run the following command from the root of the repository (do this for ai architecture assignment):

```bash
python -m actint.mcp_multiagent.smolagent
```
you will be able to see the tool calls and reasoning of each agent output in reasoning_agent.log, sql_agent.log, map_agent.log, or math_agent.log, depending on which agents are called during the execution.

to run the benchmarks on the single agent system

```bash
python -m actint.benchmarking.benchmark_agents --run-all-benchmarks
```

you can inspect llm output easily with arize ai pheonix, in another terminal run 

```bash
python -m phoenix.server.main serve
```

and make sure you have the following at the top of your smolagent.py file:

```python
from phoenix.otel import register
from openinference.instrumentation.smolagents import SmolagentsInstrumentor

register()
SmolagentsInstrumentor().instrument()
```

# Problem scope and user
## Primary User
The primary target of the ACTINT (activity intelligence) framework will be entities interested in intelligent tracking and monitering of various vehicles types, given several modalities of information. While primarily focused on military applications, this framework could extend to other fields such as shipping, public transportation, taxi fleets, and others. 
## Operational Setting
The initial main focus of this system will operate and handle AIS data tracking various vessel types. Extensions will include air traffic, and may further extend to land vehicle traffic as well.
## Core Objective
The minimal viable product of this system, will be the handling and processing of AIS data via some new data pipeline, and an LLM in the loop system that can provide intelligent information about various aspects of the data. For example, "What is ship 0001 up to right now?", and after analyzing the appropriate data, the LLM should respond with something like "based on the trajectory of ship 0001, it seems to be heading back to port."
## Entities
The the initial entities of the system will be ships only, based on time constraints, further entities can be integrated. 
## Environment Assumptions
We will assume that we have traditional AIS data information that given at some fixed rate i.e once a minute, provides information such as latitude, longitude, ship name, ship status etc.

# Inputs and Outputs
## Input data types
The primary input data type will be in tabular format containing rows of AIS data on the ships.
## Input rate
The input range will range from several times a minute,  to several times an hour as is traditional with AIS data.
## Outputs
The outputs will be in raw text format, and will come from the LLM. The LLM response should contain relevant and valuable information based on the users query. Whether we decide to restrict output to a specific type i.e json to have more predictable results will be decided later on. 
## Granularity
With regards to what level of granularity the agent should be able to reason, ideally it should be able to reason about the data as a whole i.e "Tell me which ships are coming to port 345", and about single ships i.e "What is the status of ship 123"

# Modality and task framing
Initially the model will be a text only model, being able to answer relevant queries from the user. The LLM should be able to handle several reasoning types, from small granular questions to broader hypothesis type questions.


# Model Choices
For now we will stick with open source models, and experiment with the effectiveness of smaller models like phi. If time permits/ if the reasoning capabilities of these models is too weak, then we will move on to more advanced models, and potentially test the idea of an agentic system that utilizes several models in succession to handle the reasons and data processing.

# Constraints
## Deployment
This kind of deployment will rely mainly on cloud resources, as a client-server architecture makes the most sense for development.
## Constraints
Initial beta testing will be constrained to resources on my local machine which are 

- 96 gb vram
- 64 gm ram
- 32 cores

Security requirements may require the use of self hosted LLM which mean that we should probably stay in the sub 200GB  model range. If secure cloud compute is available, then this constraint can be adjusted.

# Failures
## Possible failures
1. Hallucination: LLM models tend to give answers even when they don't have them, we will need to run thorough validation and data processing to ensure the LLM has the information that it needs in order to make the right decision, and if possible, validate that the LLM response is actually correct. 
2. Time: A system like this could be subject to time constraints, especially in emergency situations. If our LLM fails to respond in a short enough time, this could be a failure that we have to work around.
## Explainability
It could be extremely valuable for the LLM to show the information it used to draw the conclusions that it did, pulling directly from the data. That way users can be assured that what the LLM is saying is in fact correct or incorrect.

# Roadmap
## Outline
With about 12 weeks left in the semester, the roadmap for development is as follows.

Weeks 1-2: Architecture design
Weeks 2-4: First prototype development and testing
Weeks 4-6: System validation
Weeks 6-8: Further development based on validation results
Weeks 8-10: System deployment design and implementation
Weeks 10-12: Fine tuning and final adjustments
## Evaluation Metrics
Developing out the evaluation metrics for this kind of system will be difficult, as ensuring that an LLM is responding correctly is hard to automate. Simple tests can be developed however, initially verifying that the LLM is pulling the correct data given the user query, and going from there. 

