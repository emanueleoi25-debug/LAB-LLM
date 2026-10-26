from langchain_core.messages import AIMessage, HumanMessage

from assistente.model import FIXED_REPLY, FixedReplyModel


def test_fixed_reply_model_returns_constant():
    reply = FixedReplyModel().invoke([HumanMessage("x")])
    assert isinstance(reply, AIMessage) and reply.content == FIXED_REPLY
