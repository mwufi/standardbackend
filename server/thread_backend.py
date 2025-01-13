from typing import Dict, List, Optional, Type, Any, Callable
from dataclasses import dataclass
from datetime import datetime
import uuid
from sqlalchemy import create_engine, Column, String, DateTime, ForeignKey, JSON
from sqlalchemy.orm import declarative_base, Session, relationship
from sqlalchemy.pool import StaticPool
from pydantic import BaseModel
from agent_interface import AgentInterface, AnthropicAgent

Base = declarative_base()


class AgentModel(Base):
    __tablename__ = "agents"

    id = Column(String, primary_key=True)
    name = Column(String, nullable=False)
    system_prompt = Column(String, nullable=False)
    created_at = Column(DateTime, nullable=False)
    updated_at = Column(DateTime, nullable=False)

    threads = relationship("ThreadModel", back_populates="agent")
    tools = relationship("ToolModel", secondary="agent_tools", back_populates="agents")


class ThreadModel(Base):
    __tablename__ = "threads"

    id = Column(String, primary_key=True)
    agent_id = Column(String, ForeignKey("agents.id"), nullable=False)
    title = Column(String, nullable=False)
    created_at = Column(DateTime, nullable=False)
    updated_at = Column(DateTime, nullable=False)

    agent = relationship("AgentModel", back_populates="threads")
    messages = relationship("MessageModel", back_populates="thread")


class MessageModel(Base):
    __tablename__ = "messages"

    id = Column(String, primary_key=True)
    thread_id = Column(String, ForeignKey("threads.id"), nullable=False)
    agent_id = Column(String, ForeignKey("agents.id"), nullable=True)
    content = Column(String, nullable=False)
    created_at = Column(DateTime, nullable=False)

    thread = relationship("ThreadModel", back_populates="messages")
    agent = relationship("AgentModel")


class ToolModel(Base):
    __tablename__ = "tools"

    id = Column(String, primary_key=True)
    name = Column(String, nullable=False)
    description = Column(String, nullable=False)
    input_schema = Column(JSON, nullable=False)  # Store schema as JSON
    created_at = Column(DateTime, nullable=False)
    updated_at = Column(DateTime, nullable=False)

    # Optional: Add relationship to agents if you want to track which agents can use which tools
    agents = relationship("AgentModel", secondary="agent_tools")


# Junction table for many-to-many relationship between agents and tools
class AgentToolModel(Base):
    __tablename__ = "agent_tools"

    agent_id = Column(String, ForeignKey("agents.id"), primary_key=True)
    tool_id = Column(String, ForeignKey("tools.id"), primary_key=True)
    created_at = Column(DateTime, nullable=False)


# Keep the dataclass models for API responses
@dataclass
class Agent:
    id: str
    name: str
    system_prompt: str
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_db(cls, db_model: AgentModel) -> "Agent":
        return cls(
            id=db_model.id,
            name=db_model.name,
            system_prompt=db_model.system_prompt,
            created_at=db_model.created_at,
            updated_at=db_model.updated_at,
        )


@dataclass
class Thread:
    id: str
    agent_id: str
    title: str
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_db(cls, db_model: ThreadModel) -> "Thread":
        return cls(
            id=db_model.id,
            agent_id=db_model.agent_id,
            title=db_model.title,
            created_at=db_model.created_at,
            updated_at=db_model.updated_at,
        )


@dataclass
class Message:
    id: str
    thread_id: str
    agent_id: Optional[str]
    content: str
    created_at: datetime

    @classmethod
    def from_db(cls, db_model: MessageModel) -> "Message":
        return cls(
            id=db_model.id,
            thread_id=db_model.thread_id,
            agent_id=db_model.agent_id,
            content=db_model.content,
            created_at=db_model.created_at,
        )


@dataclass
class Tool:
    id: str
    name: str
    description: str
    input_schema: Dict[str, Any]
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_db(cls, db_model: ToolModel) -> "Tool":
        return cls(
            id=db_model.id,
            name=db_model.name,
            description=db_model.description,
            input_schema=db_model.input_schema,
            created_at=db_model.created_at,
            updated_at=db_model.updated_at,
        )


class ThreadBackend:
    def __init__(self, db_url: str = "sqlite:///threads.db"):
        self.engine = create_engine(
            db_url, connect_args={"check_same_thread": False}, poolclass=StaticPool
        )
        Base.metadata.create_all(self.engine)
        self.agent_implementations: Dict[str, AgentInterface] = {}

    def create_agent(
        self, name: str, system_prompt: str, tools: Optional[List] = None
    ) -> Agent:
        with Session(self.engine) as session:
            now = datetime.utcnow()
            agent_id = str(uuid.uuid4())

            db_agent = AgentModel(
                id=agent_id,
                name=name,
                system_prompt=system_prompt,
                created_at=now,
                updated_at=now,
            )
            session.add(db_agent)
            session.commit()

            # Create the implementation
            self.agent_implementations[agent_id] = AnthropicAgent(
                name=name, system_prompt=system_prompt, tools=tools
            )

            return Agent.from_db(db_agent)

    def update_agent(
        self,
        agent_id: str,
        name: Optional[str] = None,
        system_prompt: Optional[str] = None,
    ) -> Agent:
        with Session(self.engine) as session:
            db_agent = session.query(AgentModel).filter_by(id=agent_id).first()
            if not db_agent:
                raise ValueError(f"Agent {agent_id} not found")

            if name is not None:
                db_agent.name = name
            if system_prompt is not None:
                db_agent.system_prompt = system_prompt

            db_agent.updated_at = datetime.utcnow()
            session.commit()
            return Agent.from_db(db_agent)

    def create_thread(self, agent_id: str, title: str) -> Thread:
        with Session(self.engine) as session:
            if not session.query(AgentModel).filter_by(id=agent_id).first():
                raise ValueError(f"Agent {agent_id} not found")

            now = datetime.utcnow()
            thread_id = str(uuid.uuid4())
            db_thread = ThreadModel(
                id=thread_id,
                agent_id=agent_id,
                title=title,
                created_at=now,
                updated_at=now,
            )
            session.add(db_thread)

            # Create the thread in the agent implementation
            agent_impl = self.agent_implementations.get(agent_id)
            if agent_impl:
                agent_impl.create_thread(thread_id)

            session.commit()
            return Thread.from_db(db_thread)

    def add_message(
        self, thread_id: str, content: str, agent_id: Optional[str] = None
    ) -> Message:
        with Session(self.engine) as session:
            thread = session.query(ThreadModel).filter_by(id=thread_id).first()
            if not thread:
                raise ValueError(f"Thread {thread_id} not found")

            # If this is a user message
            if agent_id is None:
                db_message = MessageModel(
                    id=str(uuid.uuid4()),
                    thread_id=thread_id,
                    agent_id=None,
                    content=content,
                    created_at=datetime.utcnow(),
                )
                session.add(db_message)
                session.commit()
                user_message = Message.from_db(db_message)

                # Get agent response
                agent_impl = self.agent_implementations.get(thread.agent_id)
                if agent_impl:
                    messages = agent_impl.send_message(content, thread_id)
                    # Store the last message from the agent
                    if messages:
                        last_message = messages[-1]
                        if isinstance(last_message.get("content"), list):
                            # Handle structured content (like tool uses)
                            content = str(last_message["content"])
                        else:
                            content = last_message.get("content", "")

                        db_message = MessageModel(
                            id=str(uuid.uuid4()),
                            thread_id=thread_id,
                            agent_id=thread.agent_id,
                            content=content,
                            created_at=datetime.utcnow(),
                        )
                        session.add(db_message)
                        session.commit()

                return user_message

            # If this is an agent message
            if not session.query(AgentModel).filter_by(id=agent_id).first():
                raise ValueError(f"Agent {agent_id} not found")

            db_message = MessageModel(
                id=str(uuid.uuid4()),
                thread_id=thread_id,
                agent_id=agent_id,
                content=content,
                created_at=datetime.utcnow(),
            )
            session.add(db_message)
            session.commit()
            return Message.from_db(db_message)

    def get_thread_messages(self, thread_id: str) -> List[Message]:
        with Session(self.engine) as session:
            if not session.query(ThreadModel).filter_by(id=thread_id).first():
                raise ValueError(f"Thread {thread_id} not found")

            messages = session.query(MessageModel).filter_by(thread_id=thread_id).all()
            return [Message.from_db(msg) for msg in messages]

    def get_agent(self, agent_id: str) -> Agent:
        with Session(self.engine) as session:
            db_agent = session.query(AgentModel).filter_by(id=agent_id).first()
            if not db_agent:
                raise ValueError(f"Agent {agent_id} not found")
            return Agent.from_db(db_agent)

    def get_thread(self, thread_id: str) -> Thread:
        with Session(self.engine) as session:
            db_thread = session.query(ThreadModel).filter_by(id=thread_id).first()
            if not db_thread:
                raise ValueError(f"Thread {thread_id} not found")
            return Thread.from_db(db_thread)

    def create_tool(
        self, name: str, description: str, input_schema: Type[BaseModel]
    ) -> Tool:
        with Session(self.engine) as session:
            now = datetime.utcnow()
            db_tool = ToolModel(
                id=str(uuid.uuid4()),
                name=name,
                description=description,
                input_schema=input_schema.model_json_schema(),
                created_at=now,
                updated_at=now,
            )
            session.add(db_tool)
            session.commit()
            return Tool.from_db(db_tool)

    def assign_tool_to_agent(self, agent_id: str, tool_id: str) -> None:
        with Session(self.engine) as session:
            if not session.query(AgentModel).filter_by(id=agent_id).first():
                raise ValueError(f"Agent {agent_id} not found")
            if not session.query(ToolModel).filter_by(id=tool_id).first():
                raise ValueError(f"Tool {tool_id} not found")

            agent_tool = AgentToolModel(
                agent_id=agent_id,
                tool_id=tool_id,
                created_at=datetime.utcnow(),
            )
            session.add(agent_tool)
            session.commit()

    def get_agent_tools(self, agent_id: str) -> List[Tool]:
        with Session(self.engine) as session:
            agent = session.query(AgentModel).filter_by(id=agent_id).first()
            if not agent:
                raise ValueError(f"Agent {agent_id} not found")
            return [Tool.from_db(tool) for tool in agent.tools]

    def get_tool(self, tool_id: str) -> Tool:
        with Session(self.engine) as session:
            db_tool = session.query(ToolModel).filter_by(id=tool_id).first()
            if not db_tool:
                raise ValueError(f"Tool {tool_id} not found")
            return Tool.from_db(db_tool)

    def update_tool(
        self,
        tool_id: str,
        name: Optional[str] = None,
        description: Optional[str] = None,
        input_schema: Optional[Type[BaseModel]] = None,
    ) -> Tool:
        with Session(self.engine) as session:
            db_tool = session.query(ToolModel).filter_by(id=tool_id).first()
            if not db_tool:
                raise ValueError(f"Tool {tool_id} not found")

            if name is not None:
                db_tool.name = name
            if description is not None:
                db_tool.description = description
            if input_schema is not None:
                db_tool.input_schema = input_schema.model_json_schema()

            db_tool.updated_at = datetime.utcnow()
            session.commit()
            return Tool.from_db(db_tool)

    def get_agent_threads(self, agent_id: str) -> List[Thread]:
        with Session(self.engine) as session:
            if not session.query(AgentModel).filter_by(id=agent_id).first():
                raise ValueError(f"Agent {agent_id} not found")

            threads = session.query(ThreadModel).filter_by(agent_id=agent_id).all()
            return [Thread.from_db(thread) for thread in threads]
