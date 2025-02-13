## Table of contents for all documentation

All documentation for the UCSD Active Brain Atlas project is stored in Github under this location. The documents are split between
User and Programmer. 

### User documentation
1. [A description of the CZI to Neuroglancer process with detailed instructions](user/description.czi.2.neuroglancer.md)
1. [HOWTO run the entire CZI to Neuroglancer process process with step by step instructions](user/running.czi.2.neuroglancer.md)
1. Neuroglancer
    1. [Neuroglancer help for end users](user/neuroglancer.help.md)
    1. [Adding annotation layers](user/adding.annotation.layers.md)

### Programmer documentation
1. [A high level design of all our projects](programmer/high.level.overall.design.of.projects.md)
1. [A glossary of terms we use](programmer/Glossary.md)
1. Annotations
    1. [A description of the annotation process](programmer/annotation/3Dshapes.md)
1. Classes
    1. [Atlas class](programmer/Atlas.Class.md)
    1. [Cell dectector class](programmer/CellDetector.Class.md)
    1. [Django class](https://activebrainatlasadmin.readthedocs.io)
    1. [Pipeline class](programmer/Pipeline.Class.md)
1. Database documentation
    1. [A list of the database tables](programmer/database/Database.tables.md)
    1. [Current database information being used by the REST API with Neuroglancer](https://activebrainatlasadmin.readthedocs.io)
1. Django documentation
    1. [Releasing a new version of Django on the web server](programmer/django/releasing.new.database.portal.md)
    1. [Running tasks in the background with Supervisord](programmer/django/supervisord.md)
    1. [Creating and running unit tests for Django REST](programmer/django/django.testing.md)
    1. [Using authentication with Django/Rest](programmer/django/django.rest.auth.md)
1. Neuroglancer documentation
    1. [Doing QC on an image stack in Neuroglancer](programmer/neuroglancer/qc.on.image.stack.in.neuroglancer.md)
    1. [Affine transformation with a description of Yuncong's process](programmer/affine.transformation.md)
    1. [Neuroglancer technical documentation by Junjie](programmer/neuroglancer/neuroglancer.technical.documentation.md)
1. Preprocessing pipeline
    1. [A high level overview of the preprocessing pipeline](programmer/preprocessing-pipeline/high.level.description.of.preprocessing.pipeline.md)
    1. [Setting up the software and installation for running the preprocessing pipeline](programmer/preprocessing-pipeline/software.installation.md)
    1. [The original Yuncong Elastix parameter map](programmer/preprocessing-pipeline/elastix.parameter.map)
