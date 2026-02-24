# intersearch

Shared embedding and search infrastructure for the Interverse ecosystem.

## What this does

intersearch provides sentence-transformer embeddings and Exa web search as a common dependency for other plugins. It's infrastructure, not a user-facing tool: interject and interflux consume it as a path dependency rather than something you'd install and use directly.

If you're building a plugin that needs semantic search or web retrieval, intersearch gives you a consistent interface without each plugin reimplementing its own embedding pipeline.

## Installation

First, add the [interagency marketplace](https://github.com/mistakeknot/interagency-marketplace) (one-time setup):

```bash
/plugin marketplace add mistakeknot/interagency-marketplace
```

Then install the plugin:

```bash
/plugin install intersearch
```

Typically installed automatically as a dependency of interject or interflux rather than on its own.
