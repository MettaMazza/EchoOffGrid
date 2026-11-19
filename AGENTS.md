# EchoLite ownership

EchoLite is developed independently and in parallel. Its maintainers own its interface, configuration, defaults, model selection and runtime behaviour.

EchoOffGrid owns the bridge: locating or installing a supplied EchoLite build, providing its required files, opening its interface in the workstation and verifying the integration. Consume the upstream interface and configuration as supplied. Keep EchoLite preferences in EchoLite. Treat its development checkout as read-only. Changes to EchoLite itself, including local patches to a vendored copy, belong in the EchoLite project under its maintainers’ direction.

When an integration requires an upstream change, document the dependency for the user and continue any independent bridge work.
