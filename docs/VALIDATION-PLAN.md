# Further validation — not yet performed

Work to date includes one eight-hour historical Bitcoin window, its one-hour prefix, and a short synthetic-market demonstration. The reviewed public result bundles contain the eight-hour window and a [two-week hourly replay](../results/two-week-hourly/README.md) of the loss-sensitive profile. The two-week window overlaps the earlier run and is not the previously unused window proposed below. All profiles are deterministic comparisons from the same initial brain; these are not independent repeated trials or out-of-sample evaluations.

The next experiment should lock the existing settings, select a previously unused chronological market window before inspecting performance, and use `experiments/validation-profiles.json`. That file adds **no-external-feedback**, with learning enabled but both external reinforcement multipliers set to zero. It has not been included in the published measured results.

The extra control distinguishes external portfolio feedback from weight changes driven by endogenous activity. The frozen profile separately keeps all candidate memory efficacies fixed. Compare actions, gate activity, exposure, costs and changes to connections, not only final portfolio value.

Further work:

- Repeat across multiple non-overlapping market windows without retuning on the evaluation data.
- Add shuffled-feedback and learned-weight-reset controls; test retention on held-out inputs.
- Test whether useful conditioning works on a predictable synthetic task.
- Compare exposure-matched baselines and vary fee assumptions in separately labeled experiments.
- Investigate the fixed decoder and visual representation. Many HOLD outputs reflect absent gate spikes, and many BUY proposals are rejected by the exposure limit.
- Study market-to-neural clock choices explicitly. The current eight-hour replay advances only 48 neural seconds, far shorter than several model memory time constants.

The question is whether reinforcement produces reproducible, useful behavioral changes. Changes in spikes, weights or actions alone are insufficient to establish that.
