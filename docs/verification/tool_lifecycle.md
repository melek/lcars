# Tool Factory Lifecycle

## Data Structure
A collection of tool entries, each identified by a unique string ID.
Each entry has:
- `id`: a unique string identifier
- `invocations`: a non-negative integer counting total uses (starts at 0)
- `successes`: a non-negative integer counting successful uses (starts at 0)
- `tier`: an integer encoding the tool's promotion level: 0 = Candidate, 1 = Standard, 2 = Promoted
- `status`: an integer encoding the lifecycle state: 0 = Staged, 1 = Active, 2 = Archived
- `has_script`: a boolean indicating whether a script file exists for this entry

The registry is represented as a sequence of entries. No two entries may share the same ID.

## Operations
1. **Create(id, tier)**: Add a new entry with the given ID. The entry must not already exist. The new entry has tier set to the given value, invocations and successes both at 0, status set to Active (1), and has_script set to true. After the operation, exactly one entry has that ID.
2. **RecordUsage(id, success)**: Find the entry with the given ID (it must exist and be Active). Increment invocations by 1. If success is true, also increment successes by 1.
3. **Promote(id)**: Find the entry with the given ID (it must exist). If tier is Candidate (0), set it to Standard (1). If tier is Standard (1), set it to Promoted (2). If tier is already Promoted (2), do nothing. Tier never increases by more than one step.
4. **Archive(id)**: Find the entry with the given ID (it must exist and be Active). Set status to Archived (2). The entry remains in the collection — it is never removed. Invocations, successes, and tier are unchanged.
5. **Restore(id)**: Find the entry with the given ID (it must exist and be Archived). Set status to Active (1). Invocations, successes, and tier are unchanged.
6. **Delete(id)**: Find the entry with the given ID (it must exist). Remove it from the collection entirely.
7. **Count()**: Return the number of entries in the registry.
8. **Lookup(id)**: Return whether an entry with the given ID exists.

## Properties to Prove
- **Unique IDs**: After any sequence of operations (except Delete which removes), no two entries in the registry share the same ID. Create requires the ID not to exist beforehand.
- **Monotonic invocations**: RecordUsage only increments invocations. The invocations count for any entry never decreases across RecordUsage, Promote, Archive, and Restore operations.
- **Fitness consistency**: For every entry, successes is always less than or equal to invocations.
- **Promotion one-step**: Promote changes tier by at most one step. After Promote, tier is at most one greater than before. Tier never exceeds 2.
- **Archive preserves stats**: After Archive, the entry's invocations, successes, and tier are identical to their values before the operation.
- **Restore preserves stats**: After Restore, the entry's invocations, successes, and tier are identical to their values before the operation.
- **Script integrity**: After Create, the entry's has_script is true. Archive and Restore do not change has_script.
- **Count is read-only**: Count does not modify the registry.
- **Lookup is read-only**: Lookup does not modify the registry.
