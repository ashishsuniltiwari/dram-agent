# Copyright 2026 Google LLC
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#     https://www.apache.org/licenses/LICENSE-2.0

from google.adk.workflow import Workflow, START
from google.adk.apps import App
from agents.intake_agent import intake_agent
from agents.assessor_agent import assessor_agent
from agents.allocation_agent import allocation_agent

dram_workflow = Workflow(
    name="dram_workflow",
    edges=[
        (START, intake_agent),
        (intake_agent, assessor_agent),
        (assessor_agent, allocation_agent),
    ]
)

app = App(
    root_agent=dram_workflow,
    name="dram-app",
)

if __name__ == "__main__":
    print("DRAM App initialized successfully.")
