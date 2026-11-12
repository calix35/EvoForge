"""Register a user-owned evaluator without changing EvoForge's core."""

from pathlib import Path

from evoforge.adapters.examples import register_builtin_example_plugins
from evoforge.config import SimulatorConfig, load_experiment_config
from evoforge.core import Experiment
from evoforge.domain import EvaluationRecord, Solution


class ShiftedSphere:
    """Minimal deterministic simulator for a plugin-registration walkthrough."""

    plugin_id = "user.shifted_sphere"

    def configure(self, config: object) -> None:
        if not isinstance(config, SimulatorConfig):
            raise TypeError("Expected SimulatorConfig.")
        if config.parameters:
            raise ValueError("This example accepts no simulator parameters.")

    def evaluate(self, solution: Solution) -> EvaluationRecord:
        return EvaluationRecord(
            solution=solution,
            objective_values={
                "loss": sum((float(x) - 1.0) ** 2 for x in solution.values.values())
            },
            source=self.plugin_id,
        )


def main(output: Path = Path("results/custom_simulator")):
    config = load_experiment_config(
        Path(__file__).resolve().with_name("sphere_random_search.yaml")
    )
    config.experiment.name = "custom_simulator"
    config.problem.objectives[0].name = "loss"
    config.evaluator.simulator = SimulatorConfig(plugin=ShiftedSphere.plugin_id)
    config.outputs.directory = str(output)
    registry = register_builtin_example_plugins()
    registry.register(ShiftedSphere())
    result = Experiment(config, registry).run()
    print(f"{result.status.value}: {len(result.records)} real evaluations")
    return result


if __name__ == "__main__":
    main()
