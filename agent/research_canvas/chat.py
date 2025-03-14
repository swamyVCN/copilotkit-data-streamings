"""Chat Node"""

from typing import List, cast, Literal
from langchain_core.runnables import RunnableConfig
from langchain_core.messages import SystemMessage, AIMessage, ToolMessage
from langchain.tools import tool
from langgraph.types import Command
from copilotkit.langgraph import copilotkit_customize_config
from research_canvas.state import AgentState
from research_canvas.model import get_model
from research_canvas.download import get_resource


@tool
def Search(queries: List[str]):  # pylint: disable=invalid-name,unused-argument
    """A list of one or more search queries to find good resources to support the research."""


@tool
def WriteReport(report: str):  # pylint: disable=invalid-name,unused-argument
    """Write the research report."""


@tool
def WriteResearchQuestion(
    research_question: str,
):  # pylint: disable=invalid-name,unused-argument
    """Write the research question."""


@tool
def DeleteResources(urls: List[str]):  # pylint: disable=invalid-name,unused-argument
    """Delete the URLs from the resources."""


@tool
def add_numbers(a: float, b: float) -> float:
    """Add two numbers together."""
    return a + b


@tool
def subtract_numbers(a: float, b: float) -> float:
    """Subtract the second number from the first."""
    return a - b


@tool
def multiply_numbers(a: float, b: float) -> float:
    """Multiply two numbers together."""
    return a * b


tools = {
    "add_numbers": add_numbers,
    "subtract_numbers": subtract_numbers,
    "multiply_numbers": multiply_numbers,
}


async def chat_node(
    state: AgentState, config: RunnableConfig
) -> Command[Literal["search_node", "chat_node", "delete_node", "__end__"]]:
    """
    Chat Node
    """

    config = copilotkit_customize_config(
        config,
        emit_intermediate_state=[
            {
                "state_key": "report",
                "tool": "WriteReport",
                "tool_argument": "report",
            },
            {
                "state_key": "research_question",
                "tool": "WriteResearchQuestion",
                "tool_argument": "research_question",
            },
        ],
    )

    state["resources"] = state.get("resources", [])
    research_question = state.get("research_question", "")
    report = state.get("report", "")

    resources = []

    for resource in state["resources"]:
        content = get_resource(resource["url"])
        if content == "ERROR":
            continue
        resources.append({**resource, "content": content})

    model = get_model(state)
    # Prepare the kwargs for the ainvoke method
    ainvoke_kwargs = {}
    if model.__class__.__name__ in ["ChatOpenAI"]:
        ainvoke_kwargs["parallel_tool_calls"] = False

    response = await model.bind_tools(
        [
            Search,
            WriteReport,
            WriteResearchQuestion,
            DeleteResources,
            add_numbers,
            subtract_numbers,
            multiply_numbers,
        ],
        **ainvoke_kwargs,  # Pass the kwargs conditionally
    ).ainvoke(
        [
            # SystemMessage(
            #     content=f"""
            # You are a research assistant. You help the user with writing a research report.
            # Do not recite the resources, instead use them to answer the user's question.
            # You should use the search tool to get resources before answering the user's question.
            # If you finished writing the report, ask the user proactively for next steps, changes etc, make it engaging.
            # To write the report, you should use the WriteReport tool. Never EVER respond with the report, only use the tool.
            # If a research question is provided, YOU MUST NOT ASK FOR IT AGAIN.
            # This is the research question:
            # {research_question}
            # This is the research report:
            # {report}
            # Here are the resources that you have available:
            # {resources}
            # """
            # ),
            SystemMessage(
                content="""You are MathOpsGPT, an expert mathematics assistant specialized in performing arithmetic operations.
                    When mathematical tasks appear:
                    - Identify the type of operation required (addition, subtraction, multiplication)
                    - Use the appropriate tool to calculate the result
                    - Explain the calculation process clearly
                    - Always use math tools to calculate the result

                    You have access to the following tools:
                    - add_numbers: For adding two or more numbers together
                    - subtract_numbers: For subtracting one number from another
                    - multiply_numbers: For multiplying two or more numbers together

                    """
            ),
            *state["messages"],
        ],
        config,
    )

    ai_message = cast(AIMessage, response)
    print(f"ai_message: {ai_message}")

    if ai_message.tool_calls:
        if ai_message.tool_calls[0]["name"] == "WriteReport":
            report = ai_message.tool_calls[0]["args"].get("report", "")
            return Command(
                goto="chat_node",
                update={
                    "report": report,
                    "messages": [
                        ai_message,
                        ToolMessage(
                            tool_call_id=ai_message.tool_calls[0]["id"],
                            content="Report written.",
                        ),
                    ],
                },
            )
        if ai_message.tool_calls[0]["name"] == "WriteResearchQuestion":
            return Command(
                goto="chat_node",
                update={
                    "research_question": ai_message.tool_calls[0]["args"][
                        "research_question"
                    ],
                    "messages": [
                        ai_message,
                        ToolMessage(
                            tool_call_id=ai_message.tool_calls[0]["id"],
                            content="Research question written.",
                        ),
                    ],
                },
            )
        if ai_message.tool_calls[0]["name"] == "add_numbers":
            for tool_call in ai_message.tool_calls:
                tool = tool_call["name"]
                args = tool_call["args"]
                print(f"tool: {tool}, args: {args}")
                result = await tools[tool].ainvoke(args)
                
                state["logs"] = state.get("logs", [])
                state["logs"].append(
                    {
                        "message": f"running command {tool}",
                        "done": True,
                        "result": result,
                    }
                )
                
                message_to_append = {
                    "role": "tool",
                    "content": result,
                    "tool_call_id": tool_call["id"],
                    "name": tool_call["name"],
                } 
                # return {"messages": [message_to_append]}
                return Command(
                    goto="chat_node",
                    update={"messages": [ai_message, message_to_append]},
                )
        if ai_message.tool_calls[0]["name"] == "subtract_numbers":
            for tool_call in ai_message.tool_calls:
                tool = tool_call["name"]
                args = tool_call["args"]
                print(f"tool: {tool}, args: {args}")
                result = await tools[tool].ainvoke(args)
                state["logs"] = state.get("logs", [])
                state["logs"].append(
                    {
                        "message": f"running command {tool}",
                        "done": True,
                        "result": result,
                    }
                )
                message_to_append = {
                    "role": "tool",
                    "content": result,
                    "tool_call_id": tool_call["id"],
                    "name": tool_call["name"],
                }
                # return {"messages": [message_to_append]}

                return Command(
                    goto="chat_node",
                    update={"messages": [ai_message, message_to_append]},
                )
        if ai_message.tool_calls[0]["name"] == "multiply_numbers":
            for tool_call in ai_message.tool_calls:
                tool = tool_call["name"]
                args = tool_call["args"]
                print(f"tool: {tool}, args: {args}")
                result = await tools[tool].ainvoke(args)
                state["logs"] = state.get("logs", [])
                state["logs"].append(
                    {
                        "message": f"running command {tool}",
                        "done": True,
                        "result": result,
                    }
                )
                message_to_append = {
                    "role": "tool",
                    "content": result,
                    "tool_call_id": tool_call["id"],
                    "name": tool_call["name"],
                }
                # return {"messages": [message_to_append]}

                return Command(
                    goto="chat_node",
                    update={"messages": [ai_message, message_to_append]},
                )

    goto = "__end__"
    if ai_message.tool_calls and ai_message.tool_calls[0]["name"] == "Search":
        goto = "search_node"
    elif (
        ai_message.tool_calls and ai_message.tool_calls[0]["name"] == "DeleteResources"
    ):
        goto = "delete_node"

    return Command(goto=goto, update={"messages": response})
