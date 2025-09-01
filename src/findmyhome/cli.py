from __future__ import annotations

import argparse
import json
import sys

from .workflow import compile_workflow


def cmd_chat(args):
    workflow = compile_workflow()
    config_dict = {"configurable": {"thread_id": args.thread_id, "user_id": args.user_id}}
    print("FindMyHome chat. Type 'exit' to quit.")
    while True:
        try:
            user_query = input("You: ")
        except EOFError:
            break
        if user_query.strip().lower() in {"exit", "quit"}:
            break
        state = workflow.invoke({"user_query": [user_query]}, config=config_dict)
        # Prefer the final combined summary keys
        answer = (
            (state.get("augmentation_summary") or "")
            or ("\n".join(state.get("graph_db_agent", []) or []) )
            or ("\n".join(state.get("discussion", []) or []) )
            or state.get("invalid", "")
        )
        print("Agent:", answer)


def cmd_query(args):
    workflow = compile_workflow()
    config_dict = {"configurable": {"thread_id": args.thread_id, "user_id": args.user_id}}
    state = workflow.invoke({"user_query": [args.text]}, config=config_dict)
    print(json.dumps(state, default=str, indent=2))


def main(argv=None):
    argv = argv or sys.argv[1:]
    parser = argparse.ArgumentParser(prog="findmyhome")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_chat = sub.add_parser("chat", help="Interactive chat loop")
    p_chat.add_argument("--thread-id", default="1")
    p_chat.add_argument("--user-id", default="2")
    p_chat.set_defaults(func=cmd_chat)

    p_q = sub.add_parser("query", help="One-shot query; prints final state")
    p_q.add_argument("text", help="User query text")
    p_q.add_argument("--thread-id", default="1")
    p_q.add_argument("--user-id", default="2")
    p_q.set_defaults(func=cmd_query)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())

