# System Design Documentation

This directory contains the implemented architecture, internal protocols, and
other system-design contracts of nanoPyCodeAgent. These documents describe the
system as it exists. Proposals that are still under discussion should be
clearly marked as RFCs; durable decision rationale belongs in an ADR when the
choice is costly to reverse or otherwise surprising.

System-design documents are bilingual and split by language:

- [`zh-CN/`](zh-CN/) — **hand-written Chinese source** (source of truth)
- [`en/`](en/) — **English, generated from the Chinese source** (do not edit by
  hand)

Write or revise the Chinese source first. Before a pull request containing the
change is opened or updated for review, translate or refresh the entire
corresponding English file. The agent preparing or landing the pull request
must report whether the two versions are in sync.

These documents use the domain language defined in [`CONTEXT.md`](../../CONTEXT.md).
They complement, rather than replace:

- [`../research/`](../research/) for pre-implementation investigation;
- [`../dev_notes/`](../dev_notes/) for release-series development notes; and
- [`../superpowers/specs/`](../superpowers/specs/) for implementation plans and
  design proposals associated with a particular piece of work.

## Documents

- Event Journal Protocol v1:
  [English](en/event-journal-protocol-v1.md) |
  [Chinese](zh-CN/event-journal-protocol-v1.md)
