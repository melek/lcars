datatype ToolEntry = ToolEntry(id: string, invocations: int, successes: int, tier: int, status: int, has_script: bool)

class ToolRegistry {
  var entries: seq<ToolEntry>

  predicate Valid()
    reads this
  {
    (forall i :: 0 <= i < |entries| ==>
      entries[i].invocations >= 0 &&
      entries[i].successes >= 0 &&
      entries[i].successes <= entries[i].invocations &&
      0 <= entries[i].tier <= 2 &&
      0 <= entries[i].status <= 2) &&
    (forall i, j :: 0 <= i < |entries| && 0 <= j < |entries| && i != j ==>
      entries[i].id != entries[j].id)
  }

  constructor()
    ensures Valid()
    ensures entries == []
  {
    entries := [];
  }

  function FindIndex(id: string): int
    reads this
  {
    FindIndexInSeq(entries, id)
  }

  static function FindIndexInSeq(s: seq<ToolEntry>, id: string): int
  {
    if |s| == 0 then -1
    else if s[0].id == id then 0
    else
      var rest := FindIndexInSeq(s[1..], id);
      if rest == -1 then -1 else rest + 1
  }

  static lemma FindIndexInSeqProperties(s: seq<ToolEntry>, id: string)
    ensures FindIndexInSeq(s, id) == -1 || FindIndexInSeq(s, id) >= 0
    ensures FindIndexInSeq(s, id) >= -1
    ensures FindIndexInSeq(s, id) == -1 ==> forall i :: 0 <= i < |s| ==> s[i].id != id
    ensures FindIndexInSeq(s, id) >= 0 ==> FindIndexInSeq(s, id) < |s| && s[FindIndexInSeq(s, id)].id == id
  {
    if |s| == 0 {
    } else if s[0].id == id {
    } else {
      FindIndexInSeqProperties(s[1..], id);
      var rest := FindIndexInSeq(s[1..], id);
      if rest == -1 {
        // id not in s[1..] and s[0].id != id, so id not in s
        forall i | 0 <= i < |s|
          ensures s[i].id != id
        {
          if i == 0 {
          } else {
            assert s[i] == s[1..][i - 1];
          }
        }
      } else {
        assert rest >= 0 && rest < |s[1..]|;
        assert s[1..][rest].id == id;
        assert s[rest + 1] == s[1..][rest];
      }
    }
  }

  lemma FindIndexProperties(id: string)
    requires Valid()
    ensures FindIndex(id) == -1 ==> forall i :: 0 <= i < |entries| ==> entries[i].id != id
    ensures FindIndex(id) >= 0 ==> FindIndex(id) < |entries| && entries[FindIndex(id)].id == id
  {
    FindIndexInSeqProperties(entries, id);
  }

  static lemma FindIndexUniqueness(s: seq<ToolEntry>, id: string, i: int)
    requires forall a, b :: 0 <= a < |s| && 0 <= b < |s| && a != b ==> s[a].id != s[b].id
    requires 0 <= i < |s| && s[i].id == id
    ensures FindIndexInSeq(s, id) == i
  {
    FindIndexInSeqProperties(s, id);
    var idx := FindIndexInSeq(s, id);
    // Precondition gives us s[i].id == id, so FindIndexInSeq can't return -1
    // (it would mean no element has id, contradicting s[i].id == id)
    assert idx >= 0;
    if idx != i {
      // Both s[idx] and s[i] have id == id, but idx != i contradicts uniqueness
      assert s[idx].id == s[i].id;
      assert false; // contradiction with uniqueness precondition
    }
  }

  // Helper: prove that splicing preserves uniqueness and validity
  static lemma SplicePreservesValid(old_entries: seq<ToolEntry>, idx: int, newEntry: ToolEntry)
    requires forall i :: 0 <= i < |old_entries| ==>
      old_entries[i].invocations >= 0 &&
      old_entries[i].successes >= 0 &&
      old_entries[i].successes <= old_entries[i].invocations &&
      0 <= old_entries[i].tier <= 2 &&
      0 <= old_entries[i].status <= 2
    requires forall i, j :: 0 <= i < |old_entries| && 0 <= j < |old_entries| && i != j ==>
      old_entries[i].id != old_entries[j].id
    requires 0 <= idx < |old_entries|
    requires newEntry.id == old_entries[idx].id
    requires newEntry.invocations >= 0
    requires newEntry.successes >= 0
    requires newEntry.successes <= newEntry.invocations
    requires 0 <= newEntry.tier <= 2
    requires 0 <= newEntry.status <= 2
    ensures var new_entries := old_entries[..idx] + [newEntry] + old_entries[idx+1..];
      |new_entries| == |old_entries| &&
      (forall i :: 0 <= i < |new_entries| ==>
        new_entries[i].invocations >= 0 &&
        new_entries[i].successes >= 0 &&
        new_entries[i].successes <= new_entries[i].invocations &&
        0 <= new_entries[i].tier <= 2 &&
        0 <= new_entries[i].status <= 2) &&
      (forall i, j :: 0 <= i < |new_entries| && 0 <= j < |new_entries| && i != j ==>
        new_entries[i].id != new_entries[j].id)
  {
    var new_entries := old_entries[..idx] + [newEntry] + old_entries[idx+1..];
    assert |new_entries| == |old_entries|;
    forall i | 0 <= i < |new_entries|
      ensures new_entries[i].invocations >= 0
      ensures new_entries[i].successes >= 0
      ensures new_entries[i].successes <= new_entries[i].invocations
      ensures 0 <= new_entries[i].tier <= 2
      ensures 0 <= new_entries[i].status <= 2
    {
      if i < idx {
        assert new_entries[i] == old_entries[i];
      } else if i == idx {
        assert new_entries[i] == newEntry;
      } else {
        assert new_entries[i] == old_entries[i];
      }
    }
    forall i, j | 0 <= i < |new_entries| && 0 <= j < |new_entries| && i != j
      ensures new_entries[i].id != new_entries[j].id
    {
      if i < idx && j < idx {
        assert new_entries[i] == old_entries[i];
        assert new_entries[j] == old_entries[j];
      } else if i == idx && j < idx {
        assert new_entries[i].id == newEntry.id == old_entries[idx].id;
        assert new_entries[j] == old_entries[j];
      } else if i < idx && j == idx {
        assert new_entries[j].id == newEntry.id == old_entries[idx].id;
        assert new_entries[i] == old_entries[i];
      } else if i > idx && j > idx {
        assert new_entries[i] == old_entries[i];
        assert new_entries[j] == old_entries[j];
      } else if i == idx && j > idx {
        assert new_entries[i].id == old_entries[idx].id;
        assert new_entries[j] == old_entries[j];
      } else if i > idx && j == idx {
        assert new_entries[j].id == old_entries[idx].id;
        assert new_entries[i] == old_entries[i];
      }
    }
  }

  method Create(id: string, tier: int)
    requires Valid()
    requires 0 <= tier <= 2
    requires FindIndex(id) == -1
    modifies this
    ensures Valid()
    ensures FindIndex(id) >= 0
    ensures FindIndex(id) < |entries|
    ensures entries[FindIndex(id)].id == id
    ensures entries[FindIndex(id)].invocations == 0
    ensures entries[FindIndex(id)].successes == 0
    ensures entries[FindIndex(id)].tier == tier
    ensures entries[FindIndex(id)].status == 1
    ensures entries[FindIndex(id)].has_script == true
    ensures |entries| == |old(entries)| + 1
    ensures forall i :: 0 <= i < |old(entries)| ==> entries[i] == old(entries)[i]
  {
    FindIndexProperties(id);
    var newEntry := ToolEntry(id, 0, 0, tier, 1, true);
    entries := entries + [newEntry];
    FindIndexInSeqProperties(entries, id);
    assert entries[|entries| - 1].id == id;
    FindIndexUniqueness(entries, id, |entries| - 1);
  }

  method RecordUsage(id: string, success: bool)
    requires Valid()
    requires FindIndex(id) >= 0
    requires FindIndex(id) < |entries|
    requires entries[FindIndex(id)].status == 1
    modifies this
    ensures Valid()
    ensures |entries| == |old(entries)|
    ensures FindIndex(id) == old(FindIndex(id))
    ensures FindIndex(id) >= 0 && FindIndex(id) < |entries|
    ensures entries[FindIndex(id)].invocations == old(entries[FindIndex(id)].invocations) + 1
    ensures success ==> entries[FindIndex(id)].successes == old(entries[FindIndex(id)].successes) + 1
    ensures !success ==> entries[FindIndex(id)].successes == old(entries[FindIndex(id)].successes)
    ensures entries[FindIndex(id)].tier == old(entries[FindIndex(id)].tier)
    ensures entries[FindIndex(id)].status == old(entries[FindIndex(id)].status)
    ensures entries[FindIndex(id)].has_script == old(entries[FindIndex(id)].has_script)
    ensures forall i :: 0 <= i < |entries| && i != FindIndex(id) ==> entries[i] == old(entries)[i]
  {
    FindIndexProperties(id);
    var idx := FindIndex(id);
    var e := entries[idx];
    var newSuccesses := if success then e.successes + 1 else e.successes;
    var newEntry := ToolEntry(e.id, e.invocations + 1, newSuccesses, e.tier, e.status, e.has_script);
    SplicePreservesValid(entries, idx, newEntry);
    entries := entries[..idx] + [newEntry] + entries[idx+1..];
    FindIndexInSeqProperties(entries, id);
    FindIndexUniqueness(entries, id, idx);
  }

  method Promote(id: string)
    requires Valid()
    requires FindIndex(id) >= 0
    requires FindIndex(id) < |entries|
    modifies this
    ensures Valid()
    ensures |entries| == |old(entries)|
    ensures FindIndex(id) == old(FindIndex(id))
    ensures FindIndex(id) >= 0 && FindIndex(id) < |entries|
    ensures old(entries[FindIndex(id)].tier) == 0 ==> entries[FindIndex(id)].tier == 1
    ensures old(entries[FindIndex(id)].tier) == 1 ==> entries[FindIndex(id)].tier == 2
    ensures old(entries[FindIndex(id)].tier) == 2 ==> entries[FindIndex(id)].tier == 2
    ensures entries[FindIndex(id)].tier <= 2
    ensures entries[FindIndex(id)].tier >= old(entries[FindIndex(id)].tier)
    ensures entries[FindIndex(id)].tier <= old(entries[FindIndex(id)].tier) + 1
    ensures entries[FindIndex(id)].invocations == old(entries[FindIndex(id)].invocations)
    ensures entries[FindIndex(id)].successes == old(entries[FindIndex(id)].successes)
    ensures entries[FindIndex(id)].status == old(entries[FindIndex(id)].status)
    ensures entries[FindIndex(id)].has_script == old(entries[FindIndex(id)].has_script)
    ensures forall i :: 0 <= i < |entries| && i != FindIndex(id) ==> entries[i] == old(entries)[i]
  {
    FindIndexProperties(id);
    var idx := FindIndex(id);
    var e := entries[idx];
    var newTier := if e.tier == 0 then 1 else if e.tier == 1 then 2 else 2;
    var newEntry := ToolEntry(e.id, e.invocations, e.successes, newTier, e.status, e.has_script);
    SplicePreservesValid(entries, idx, newEntry);
    entries := entries[..idx] + [newEntry] + entries[idx+1..];
    FindIndexInSeqProperties(entries, id);
    FindIndexUniqueness(entries, id, idx);
  }

  method Archive(id: string)
    requires Valid()
    requires FindIndex(id) >= 0
    requires FindIndex(id) < |entries|
    requires entries[FindIndex(id)].status == 1
    modifies this
    ensures Valid()
    ensures |entries| == |old(entries)|
    ensures FindIndex(id) == old(FindIndex(id))
    ensures FindIndex(id) >= 0 && FindIndex(id) < |entries|
    ensures entries[FindIndex(id)].status == 2
    ensures entries[FindIndex(id)].invocations == old(entries[FindIndex(id)].invocations)
    ensures entries[FindIndex(id)].successes == old(entries[FindIndex(id)].successes)
    ensures entries[FindIndex(id)].tier == old(entries[FindIndex(id)].tier)
    ensures entries[FindIndex(id)].has_script == old(entries[FindIndex(id)].has_script)
    ensures forall i :: 0 <= i < |entries| && i != FindIndex(id) ==> entries[i] == old(entries)[i]
  {
    FindIndexProperties(id);
    var idx := FindIndex(id);
    var e := entries[idx];
    var newEntry := ToolEntry(e.id, e.invocations, e.successes, e.tier, 2, e.has_script);
    SplicePreservesValid(entries, idx, newEntry);
    entries := entries[..idx] + [newEntry] + entries[idx+1..];
    FindIndexInSeqProperties(entries, id);
    FindIndexUniqueness(entries, id, idx);
  }

  method Restore(id: string)
    requires Valid()
    requires FindIndex(id) >= 0
    requires FindIndex(id) < |entries|
    requires entries[FindIndex(id)].status == 2
    modifies this
    ensures Valid()
    ensures |entries| == |old(entries)|
    ensures FindIndex(id) == old(FindIndex(id))
    ensures FindIndex(id) >= 0 && FindIndex(id) < |entries|
    ensures entries[FindIndex(id)].status == 1
    ensures entries[FindIndex(id)].invocations == old(entries[FindIndex(id)].invocations)
    ensures entries[FindIndex(id)].successes == old(entries[FindIndex(id)].successes)
    ensures entries[FindIndex(id)].tier == old(entries[FindIndex(id)].tier)
    ensures entries[FindIndex(id)].has_script == old(entries[FindIndex(id)].has_script)
    ensures forall i :: 0 <= i < |entries| && i != FindIndex(id) ==> entries[i] == old(entries)[i]
  {
    FindIndexProperties(id);
    var idx := FindIndex(id);
    var e := entries[idx];
    var newEntry := ToolEntry(e.id, e.invocations, e.successes, e.tier, 1, e.has_script);
    SplicePreservesValid(entries, idx, newEntry);
    entries := entries[..idx] + [newEntry] + entries[idx+1..];
    FindIndexInSeqProperties(entries, id);
    FindIndexUniqueness(entries, id, idx);
  }

  method Delete(id: string)
    requires Valid()
    requires FindIndex(id) >= 0
    requires FindIndex(id) < |entries|
    modifies this
    ensures Valid()
    ensures |entries| == |old(entries)| - 1
    ensures FindIndex(id) == -1
    ensures forall e :: e in entries ==> e in old(entries)
  {
    FindIndexProperties(id);
    var idx := FindIndex(id);
    var old_entries := entries;
    entries := entries[..idx] + entries[idx+1..];

    // Prove no entry has the deleted id
    assert forall i :: 0 <= i < idx ==> entries[i] == old_entries[i];
    assert forall i :: idx <= i < |entries| ==> entries[i] == old_entries[i + 1];

    forall i | 0 <= i < |entries|
      ensures entries[i].id != id
    {
      if i < idx {
        assert entries[i] == old_entries[i];
        // old_entries[i].id != old_entries[idx].id because i != idx and Valid()
      } else {
        assert entries[i] == old_entries[i + 1];
        // old_entries[i+1].id != old_entries[idx].id because i+1 != idx and Valid()
      }
    }

    // Now FindIndexInSeqProperties can conclude FindIndex(id) == -1
    FindIndexInSeqProperties(entries, id);
  }

  method Count() returns (c: int)
    requires Valid()
    ensures Valid()
    ensures c == |entries|
    ensures entries == old(entries)
  {
    c := |entries|;
  }

  method Lookup(id: string) returns (found: bool)
    requires Valid()
    ensures Valid()
    ensures entries == old(entries)
    ensures found <==> FindIndex(id) >= 0
  {
    FindIndexProperties(id);
    var idx := FindIndex(id);
    found := idx >= 0;
  }
}

method Main()
{
  var registry := new ToolRegistry();

  // Create two tools
  registry.Create("tool1", 0);

  // After creating tool1, registry has exactly one entry: "tool1"
  // Prove tool2 is not present so Create precondition is met
  assert |registry.entries| == 1;
  assert registry.entries[0].id == "tool1";
  assert "tool1" != "tool2";
  ToolRegistry.FindIndexInSeqProperties(registry.entries, "tool2");
  registry.Create("tool2", 1);

  var c := registry.Count();
  assert c == 2;

  var found := registry.Lookup("tool1");
  assert found;

  var notFound := registry.Lookup("tool3");

  // RecordUsage on tool1
  registry.FindIndexProperties("tool1");
  registry.RecordUsage("tool1", true);

  registry.FindIndexProperties("tool1");
  registry.RecordUsage("tool1", false);

  // Promote tool1
  registry.FindIndexProperties("tool1");
  registry.Promote("tool1");

  // Archive and restore tool1
  registry.FindIndexProperties("tool1");
  registry.Archive("tool1");

  registry.FindIndexProperties("tool1");
  registry.Restore("tool1");

  // Delete tool1
  registry.FindIndexProperties("tool1");
  registry.Delete("tool1");

  var c2 := registry.Count();
  assert c2 == 1;
}
