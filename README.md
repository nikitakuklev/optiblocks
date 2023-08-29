<br/>
<div align="center">
  <h3 align="center">OptiBlocks</h3>
  <p align="center">
    Optimization components for accelerator tools
  </p>
</div>


## About
This repo contains 'mostly-standalone' pieces of apsopt that might be of interest to the community.
They can be used as is by importing the package, or feel free to just copy/paste.


## Getting started
### Prerequisites
* Python >= 3.8
* pyqt >= 5.12
* pyqt-test
* pyqtgraph

## Contents
### Pydantic parameter tree
Extension/rewrite of the pyqtgraph ParameterTree system to support reading and writing Pydantic 
models.

The key implementation challenge is how to validate and handle edits of child elements - this 
must be done in the first available parent model, but copies of fields should be avoided because 
those objects might contain other state. For now, only a subset of object types are supported: 
BaseModel, primitive types, dict, and list. Nesting to arbitrary depth should 
work fine, but note that validation/copying/assignment will always be done on per-field basis.

The structure of parameters is:

```mermaid
graph
    Model --> PrimitiveField;
    Model --> ListField;
    Model --> DictField;
    Model --> SubModel;
    ListField --> PrimitiveParameter;
    ListField --> PrimitiveContainer;
    DictField --> PrimitiveParameter2;
    DictField --> PrimitiveContainer2;
```

#### Example GUI

To accompany the pydantic tree, an example is included in the `/scripts/tree/sample_gui.py`.


### GUI testing with pyqt-test

A demonstration of GUI testing with pyqt-test is provided in `/scripts/tree/test_tree.py`. 
Unlike standard tests, GUI tests simulate interactions with various elements by setting text box 
values, pressing buttons, etc. Resulting state is then verified through the pydantic model.

