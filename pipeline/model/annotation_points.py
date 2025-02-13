
from sqlalchemy.orm import relationship
from sqlalchemy import Column, String, Integer, ForeignKey,Enum
from sqlalchemy.sql.sqltypes import Float
from model.atlas_model import Base
from model.brain_region import BrainRegion
from model.user import User
import enum

class AnnotationType(enum.Enum):
    POLYGON_SEQUENCE = 'POLYGON_SEQUENCE'
    MARKED_CELL = 'MARKED_CELL'
    STRUCTURE_COM = 'STRUCTURE_COM'

class AnnotationSession(Base):
    __tablename__ = 'annotation_session'
    id =  Column(Integer, primary_key=True, nullable=False)
    FK_prep_id = Column(String, nullable=False)
    FK_parent = Column(Integer)
    FK_annotator_id = Column(Integer, ForeignKey('auth_user.id'), nullable=True)
    FK_structure_id = Column(Integer, ForeignKey('structure.id'),nullable=True)
    annotation_type = Column(Enum(AnnotationType))    
    brain_region = relationship('BrainRegion', lazy=True)
    user = relationship('User', lazy=True)
    active =  Column(Integer,default=1)

class CellSources(enum.Enum):
    NULL = 'NULL'
    MACHINE_SURE = 'MACHINE-SURE'
    MACHINE_UNSURE = 'MACHINE-UNSURE'
    HUMAN_POSITIVE = 'HUMAN-POSITIVE'
    HUMAN_NEGATIVE = 'HUMAN-NEGATIVE'

class MarkedCell(Base):
    __tablename__ = 'marked_cells'
    id =  Column(Integer, primary_key=True, nullable=False)
    x = Column(Float, nullable=False)
    y = Column(Float, nullable=False)
    z = Column(Float, nullable=False)
    source = Column(Enum(CellSources))    
    FK_session_id = Column(Integer, ForeignKey('annotation_session.id'), nullable=True)
    FK_cell_type_id = Column(Integer)
    session = relationship('AnnotationSession', lazy=True)

class COMSources(enum.Enum):
    MANUAL = 'MANUAL'
    COMPUTER = 'COMPUTER'

class StructureCOM(Base):
    __tablename__ = 'structure_com'
    id =  Column(Integer, primary_key=True, nullable=False)
    x = Column(Float, nullable=False)
    y = Column(Float, nullable=False)
    z = Column(Float, nullable=False)
    source = Column(Enum(COMSources))    
    FK_session_id = Column(Integer, ForeignKey('annotation_session.id'), nullable=True)
    session = relationship('AnnotationSession', lazy=True)

class PolygonSources(enum.Enum):
    NA = 'NA'

class PolygonSequence(Base):
    __tablename__ = 'polygon_sequences'
    id =  Column(Integer, primary_key=True, nullable=False)
    x = Column(Float, nullable=False)
    y = Column(Float, nullable=False)
    z = Column(Float, nullable=False)
    source = Column(Enum(PolygonSources))    
    FK_session_id = Column(Integer, ForeignKey('annotation_session.id'), nullable=True)
    polygon_index = Column(Integer)
    point_order = Column(Integer)
    session = relationship('AnnotationSession', lazy=True)

class MarkedCellView(Base):
    __tablename__ = 'view_marked_cells'
    # __table__ = Table(__tablename__, Base.metadata, autoload=True, autoload_with=Engine)
    # __mapper_args__ = {'primary_key': [__table__.c.MyColumnInTable]} 
    FK_prep_id = Column(String, nullable=False,primary_key = True)
    FK_annotator_id = Column(Integer, ForeignKey('auth_user.id'), nullable=True,primary_key = True)
    FK_cell_type_id = Column(Integer, ForeignKey('cell_type.id'), nullable=True,primary_key = True)
    FK_structure_id = Column(Integer, ForeignKey('structure.id'), nullable=True,primary_key = True)
    source = Column(Enum(CellSources), nullable=False,primary_key = True)    
    active =  Column(Integer,primary_key = True)
    x = Column(Float, nullable=False,primary_key = True)
    y = Column(Float, nullable=False,primary_key = True)
    z = Column(Float, nullable=False,primary_key = True)
    # __mapper_args__ = {
    #     "primary_key":[FK_prep_id, field2]
    # }