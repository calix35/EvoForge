# Architecture

EvoForge is organized around a small set of independent layers.

```mermaid
flowchart TB
    user["User"]

    subgraph interface_layer["Interface Layer"]
        cli["CLI"]
        config_files["YAML Configuration"]
        python_api["Python API"]
    end

    subgraph core_layer["Core Layer"]
        experiment_engine["Experiment Runtime"]
        output_manager["Output Manager"]
    end

    subgraph domain_layer["Domain Layer"]
        problem_model["Problem"]
        solution_model["Solution"]
        evaluation_model["EvaluationRecord"]
        dataset_model["Dataset"]
    end

    subgraph plugin_layer["Plugin Layer"]
        registry["Plugin Registry"]
        optimizer_plugins["Optimizer Plugins"]
        simulator_plugins["Simulator Plugins"]
        surrogate_plugins["Surrogate Plugins"]
    end

    subgraph external_layer["External Libraries"]
        optimization_libraries["Optimization Libraries"]
        simulator_libraries["Simulators"]
        ml_libraries["Machine Learning Libraries"]
    end

    user --> cli
    user --> config_files
    user --> python_api

    cli --> experiment_engine
    config_files --> experiment_engine
    python_api --> experiment_engine

    experiment_engine --> problem_model
    experiment_engine --> solution_model
    experiment_engine --> evaluation_model
    experiment_engine --> dataset_model
    experiment_engine --> registry
    experiment_engine --> output_manager

    registry --> optimizer_plugins
    registry --> simulator_plugins
    registry --> surrogate_plugins

    optimizer_plugins --> optimization_libraries
    simulator_plugins --> simulator_libraries
    surrogate_plugins --> ml_libraries
```

---

## Core Boundary

The core runtime coordinates configuration loading, plugin lookup, experiment
execution, and output artifact generation.

External scientific libraries are integrated through adapter packages. The core
does not import optional dependencies such as `pymoo` or `scikit-learn`
directly.

---

## Data Flow

The executable experiment flow is:

```text
YAML configuration
    -> validated configuration
    -> domain objects
    -> plugin registry
    -> optimizer and evaluator
    -> evaluation records
    -> output artifacts
```

This keeps experiment definition, execution, evaluation provenance, and output
storage separated.
