import sqlalchemy as sq
from sqlalchemy import engine, UniqueConstraint

from sqlalchemy.orm import declarative_base, sessionmaker, relationship

Base = declarative_base()


class EnglishDict(Base):
    __tablename__ = "english"
    id = sq.Column(sq.Integer, primary_key=True)
    english_word = sq.Column(sq.String(40), unique=True, nullable=False)
    russian_word = sq.Column(sq.String(40), nullable=False)

    users = relationship('PersonalDict', back_populates='english_word_rel')


class Users(Base):
    __tablename__ = "users"
    id = sq.Column(sq.Integer, primary_key=True)
    user_id = sq.Column(sq.Integer, unique=True, nullable=False)

    words = relationship('PersonalDict', back_populates='user_rel')


class PersonalDict(Base):
    __tablename__ = "personal_dict"
    id = sq.Column(sq.Integer, primary_key=True)
    user_id = sq.Column(sq.Integer, sq.ForeignKey("users.id"), nullable=False, index=True)
    word_id = sq.Column(sq.Integer, sq.ForeignKey("english.id"), nullable=False)

    __table_args__ = (
        UniqueConstraint('user_id', 'word_id', name='unique_user_word'),
    )
    user_rel = relationship('Users', back_populates='words')
    english_word_rel = relationship('EnglishDict', back_populates='users')

def create_tables(engine):
    Base.metadata.create_all(engine)

