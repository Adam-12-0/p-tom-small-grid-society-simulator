"""Run one trace or a small repeated density comparison."""
import argparse
import json
from dataclasses import asdict
from statistics import mean
from grid_world import Config, run


def summary(config, engine="direct"):
    history = run(config, engine)
    complete = len(history[-1].informed) == config.people
    return {"config": asdict(config), "engine": engine, "complete": complete,
            "time_to_all_informed": history[-1].step if complete else None,
            "final_fraction": history[-1].fraction_informed,
            "fraction_by_step": [frame.fraction_informed for frame in history]}


def compare(size=20, counts=(10, 40, 120), trials=5, share_probability=1.0, max_steps=500):
    rows = []
    for people in counts:
        traces = [summary(Config(size=size, people=people, share_probability=share_probability,
                                 max_steps=max_steps, seed=i)) for i in range(trials)]
        completed = [t["time_to_all_informed"] for t in traces if t["complete"]]
        rows.append({"people": people, "density": people / size**2, "trials": trials,
                     "completed": len(completed),
                     "mean_steps_completed": mean(completed) if completed else None,
                     "censored_at_step": max_steps})
    return rows


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--people", type=int, default=40)
    parser.add_argument("--size", type=int, default=20)
    parser.add_argument("--seed", type=int, default=1)
    parser.add_argument("--source", choices=["center", "edge"], default="center")
    parser.add_argument("--share-probability", type=float, default=1.0)
    parser.add_argument("--max-steps", type=int, default=500)
    parser.add_argument("--engine", choices=["direct", "psl"], default="direct")
    parser.add_argument("--compare", action="store_true")
    args = parser.parse_args()
    if args.compare:
        print(json.dumps(compare(size=args.size, share_probability=args.share_probability,
                                 max_steps=args.max_steps), indent=2))
    else:
        print(json.dumps(summary(Config(size=args.size, people=args.people, seed=args.seed,
                    share_probability=args.share_probability, max_steps=args.max_steps,
                    source=args.source), args.engine), indent=2))
