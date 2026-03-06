datatype Entry = Entry(id: string, invocations: int, successes: int, tier: int, archived: bool)

class ToolRegistry {
  var entries: seq<Entry>

  predicate Valid()
    reads this
  {
    (forall i :: 0 <= i < |entries| ==> entries[i].invocations >= 0) &&
    (forall i :: 0 <= i < |entries| ==> entries[i].successes >= 0) &&
    (forall i :: 0 <= i < |entries| ==> entries[i].successes <= entries[i].invocations) &&
    (forall i :: 0 <= i < |entries| ==> 0 <= entries[i].tier <= 2) &&
    (forall i, j :: 0 <= i < |entries| && 0 <= j < |entries| && i != j ==> entries[i].id != entries[j].id)
  }

  constructor()
    ensures Valid()
    ensures entries == []
  {
    entries := [];
  }

  static function FindIndexPure(id: string, s: seq<Entry>): int
    ensures -1 <= FindIndexPure(id, s) < |s|
    ensures FindIndexPure(id, s) == -1 ==> forall k :: 0 <= k < |s| ==> s[k].id != id
    ensures FindIndexPure(id, s) >= 0 ==> s[FindIndexPure(id, s)].id == id
  {
    if |s| == 0 then -1
    else if s[0].id == id then 0
    else
      var rest := FindIndexPure(id, s[1..]);
      if rest == -1 then -1 else rest + 1
  }

  static lemma FindIndexPureCorrect(id: string, s: seq<Entry>, i: int)
    requires 0 <= i < |s|
    requires s[i].id == id
    requires forall j :: 0 <= j < i ==> s[j].id != id
    ensures FindIndexPure(id, s) == i
  {
    if i == 0 {
      assert s[0].id == id;
    } else {
      assert s[0].id != id;
      FindIndexPureCorrect(id, s[1..], i - 1);
      assert s[1..][i-1].id == id;
      assert FindIndexPure(id, s[1..]) == i - 1;
    }
  }

  static lemma FindIndexPurePreservesOthers(id: string, s: seq<Entry>, otherId: string, i: int)
    requires 0 <= i < |s|
    requires s[i].id == otherId
    requires otherId != id
    requires forall j :: 0 <= j < |s| && j != i ==> s[j].id != otherId
    ensures FindIndexPure(otherId, s) == i
  {
    FindIndexPureCorrect(otherId, s, i);
  }

  method FindIndex(id: string) returns (idx: int)
    requires Valid()
    ensures -1 <= idx < |entries|
    ensures idx == -1 ==> forall i :: 0 <= i < |entries| ==> entries[i].id != id
    ensures idx >= 0 ==> entries[idx].id == id
    ensures idx == FindIndexPure(id, entries)
  {
    idx := -1;
    var i := 0;
    while i < |entries|
      invariant 0 <= i <= |entries|
      invariant idx == -1 ==> forall k :: 0 <= k < i ==> entries[k].id != id
      invariant idx >= 0 ==> idx < |entries| && entries[idx].id == id
      invariant idx == FindIndexPure(id, entries[..i])
      decreases |entries| - i
    {
      if entries[i].id == id {
        idx := i;
        assert entries[..i+1] == entries[..i] + [entries[i]];
        FindIndexPureCorrect(id, entries, i);
        return;
      }
      assert entries[..i+1] == entries[..i] + [entries[i]];
      i := i + 1;
    }
    assert entries[..|entries|] == entries;
  }

  method Upsert(id: string, tier: int)
    requires Valid()
    requires 0 <= tier <= 2
    modifies this
    ensures Valid()
    ensures |entries| >= 1
    ensures exists i :: 0 <= i < |entries| && entries[i].id == id && entries[i].tier == tier
    ensures forall i :: 0 <= i < |entries| && entries[i].id != id ==>
              exists j :: 0 <= j < old(|entries|) && old(entries)[j].id == entries[i].id
    ensures |entries| >= old(|entries|)
    ensures forall i, j :: 0 <= i < |entries| && 0 <= j < |entries| && i != j ==> entries[i].id != entries[j].id
    ensures forall oid :: (exists j :: 0 <= j < old(|entries|) && old(entries)[j].id == oid) ==>
              (exists j :: 0 <= j < |entries| && entries[j].id == oid)
  {
    var idx := FindIndex(id);
    if idx >= 0 {
      var e := entries[idx];
      var newEntry := Entry(e.id, e.invocations, e.successes, tier, e.archived);
      var oldEntries2 := entries;
      entries := entries[..idx] + [newEntry] + entries[idx+1..];
      assert entries[idx].id == id && entries[idx].tier == tier;

      // Prove preservation: every old entry is still present (update case)
      forall oid | exists j :: 0 <= j < |oldEntries2| && oldEntries2[j].id == oid
        ensures exists j :: 0 <= j < |entries| && entries[j].id == oid
      {
        var j :| 0 <= j < |oldEntries2| && oldEntries2[j].id == oid;
        if j == idx {
          assert entries[idx].id == e.id;
          assert e.id == id;
          assert oldEntries2[idx].id == id;
          assert oid == id;
          assert entries[idx].id == oid;
        } else {
          assert entries[j] == oldEntries2[j];
          assert entries[j].id == oid;
        }
      }
    } else {
      var oldEntries := entries;
      var newEntry := Entry(id, 0, 0, tier, false);
      entries := entries + [newEntry];
      assert entries[|entries|-1].id == id && entries[|entries|-1].tier == tier;

      // Prove preservation: every old entry is still present
      forall oid | exists j :: 0 <= j < |oldEntries| && oldEntries[j].id == oid
        ensures exists j :: 0 <= j < |entries| && entries[j].id == oid
      {
        var j :| 0 <= j < |oldEntries| && oldEntries[j].id == oid;
        assert entries[j] == oldEntries[j];
        assert entries[j].id == oid;
      }
    }
  }

  method RecordUsage(id: string, success: bool)
    requires Valid()
    requires exists i :: 0 <= i < |entries| && entries[i].id == id
    modifies this
    ensures Valid()
    ensures |entries| == old(|entries|)
    ensures FindIndexPure(id, old(entries)) >= 0
    ensures exists i :: 0 <= i < |entries| && entries[i].id == id &&
              entries[i].invocations == old(entries)[FindIndexPure(id, old(entries))].invocations + 1 &&
              (success ==> entries[i].successes == old(entries)[FindIndexPure(id, old(entries))].successes + 1) &&
              (!success ==> entries[i].successes == old(entries)[FindIndexPure(id, old(entries))].successes)
    ensures forall i :: 0 <= i < |entries| && entries[i].id != id ==>
              FindIndexPure(entries[i].id, old(entries)) >= 0 &&
              entries[i] == old(entries)[FindIndexPure(entries[i].id, old(entries))]
    ensures forall oid :: (exists j :: 0 <= j < old(|entries|) && old(entries)[j].id == oid) ==>
              (exists j :: 0 <= j < |entries| && entries[j].id == oid)
  {
    var idx := FindIndex(id);
    var e := entries[idx];
    var newSuccesses := if success then e.successes + 1 else e.successes;
    var newEntry := Entry(e.id, e.invocations + 1, newSuccesses, e.tier, e.archived);
    var oldEntries := entries;
    entries := entries[..idx] + [newEntry] + entries[idx+1..];

    // Prove all entries have same IDs as before (newEntry.id == oldEntries[idx].id)
    assert newEntry.id == oldEntries[idx].id;
    assert |entries| == |oldEntries|;
    forall i | 0 <= i < |entries|
      ensures entries[i].id == oldEntries[i].id
    {
      if i < idx {
        assert entries[i] == oldEntries[i];
      } else if i == idx {
        assert entries[i] == newEntry;
        assert newEntry.id == oldEntries[idx].id;
      } else {
        assert entries[i] == oldEntries[i];
      }
    }

    // Prove UniqueIds: since all IDs are the same as before, distinctness is preserved
    forall i, j | 0 <= i < |entries| && 0 <= j < |entries| && i != j
      ensures entries[i].id != entries[j].id
    {
      assert entries[i].id == oldEntries[i].id;
      assert entries[j].id == oldEntries[j].id;
      assert oldEntries[i].id != oldEntries[j].id;
    }

    assert idx == FindIndexPure(id, oldEntries);
    assert entries[idx].id == id;
    assert entries[idx].invocations == oldEntries[idx].invocations + 1;

    forall i | 0 <= i < |entries| && entries[i].id != id
      ensures FindIndexPure(entries[i].id, oldEntries) >= 0 &&
              entries[i] == oldEntries[FindIndexPure(entries[i].id, oldEntries)]
    {
      if i < idx {
        assert entries[i] == oldEntries[i];
        assert oldEntries[i].id == entries[i].id;
        assert oldEntries[i].id != id;
        FindIndexPureCorrect(entries[i].id, oldEntries, i);
        assert FindIndexPure(entries[i].id, oldEntries) == i;
      } else if i > idx {
        assert entries[i] == oldEntries[i];
        assert oldEntries[i].id == entries[i].id;
        assert oldEntries[i].id != id;
        FindIndexPureCorrect(entries[i].id, oldEntries, i);
        assert FindIndexPure(entries[i].id, oldEntries) == i;
      }
    }

    forall oid | exists j :: 0 <= j < |oldEntries| && oldEntries[j].id == oid
      ensures exists j :: 0 <= j < |entries| && entries[j].id == oid
    {
      var j :| 0 <= j < |oldEntries| && oldEntries[j].id == oid;
      if j == idx {
        assert entries[idx].id == id;
        assert oid == id;
        assert entries[idx].id == oid;
      } else {
        assert entries[j] == oldEntries[j];
        assert entries[j].id == oid;
      }
    }
  }

  method Promote(id: string)
    requires Valid()
    requires exists i :: 0 <= i < |entries| && entries[i].id == id
    modifies this
    ensures Valid()
    ensures |entries| == old(|entries|)
    ensures FindIndexPure(id, old(entries)) >= 0
    ensures exists i :: 0 <= i < |entries| && entries[i].id == id &&
              (old(entries)[FindIndexPure(id, old(entries))].tier == 0 ==> entries[i].tier == 1) &&
              (old(entries)[FindIndexPure(id, old(entries))].tier == 1 ==> entries[i].tier == 2) &&
              (old(entries)[FindIndexPure(id, old(entries))].tier == 2 ==> entries[i].tier == 2) &&
              entries[i].tier <= old(entries)[FindIndexPure(id, old(entries))].tier + 1 &&
              entries[i].tier <= 2
    ensures forall i :: 0 <= i < |entries| && entries[i].id != id ==>
              FindIndexPure(entries[i].id, old(entries)) >= 0 &&
              entries[i] == old(entries)[FindIndexPure(entries[i].id, old(entries))]
    ensures forall oid :: (exists j :: 0 <= j < old(|entries|) && old(entries)[j].id == oid) ==>
              (exists j :: 0 <= j < |entries| && entries[j].id == oid)
  {
    var idx := FindIndex(id);
    var e := entries[idx];
    var newTier := if e.tier < 2 then e.tier + 1 else e.tier;
    var newEntry := Entry(e.id, e.invocations, e.successes, newTier, e.archived);
    var oldEntries := entries;
    entries := entries[..idx] + [newEntry] + entries[idx+1..];
    
    assert idx == FindIndexPure(id, oldEntries);
    assert entries[idx].id == id;
    
    forall i | 0 <= i < |entries| && entries[i].id != id
      ensures FindIndexPure(entries[i].id, oldEntries) >= 0 &&
              entries[i] == oldEntries[FindIndexPure(entries[i].id, oldEntries)]
    {
      if i < idx {
        assert entries[i] == oldEntries[i];
        assert oldEntries[i].id == entries[i].id;
        assert oldEntries[i].id != id;
        FindIndexPureCorrect(entries[i].id, oldEntries, i);
        assert FindIndexPure(entries[i].id, oldEntries) == i;
      } else if i > idx {
        assert entries[i] == oldEntries[i];
        assert oldEntries[i].id == entries[i].id;
        assert oldEntries[i].id != id;
        FindIndexPureCorrect(entries[i].id, oldEntries, i);
        assert FindIndexPure(entries[i].id, oldEntries) == i;
      }
    }
    
    forall oid | exists j :: 0 <= j < |oldEntries| && oldEntries[j].id == oid
      ensures exists j :: 0 <= j < |entries| && entries[j].id == oid
    {
      var j :| 0 <= j < |oldEntries| && oldEntries[j].id == oid;
      if j == idx {
        assert entries[idx].id == id;
        assert oid == id;
        assert entries[idx].id == oid;
      } else {
        assert entries[j] == oldEntries[j];
        assert entries[j].id == oid;
      }
    }
  }

  method Archive(id: string)
    requires Valid()
    requires exists i :: 0 <= i < |entries| && entries[i].id == id
    modifies this
    ensures Valid()
    ensures |entries| == old(|entries|)
    ensures exists i :: 0 <= i < |entries| && entries[i].id == id && entries[i].archived == true
    ensures forall i :: 0 <= i < |entries| && entries[i].id != id ==>
              FindIndexPure(entries[i].id, old(entries)) >= 0 &&
              entries[i] == old(entries)[FindIndexPure(entries[i].id, old(entries))]
    ensures forall oid :: (exists j :: 0 <= j < old(|entries|) && old(entries)[j].id == oid) ==>
              (exists j :: 0 <= j < |entries| && entries[j].id == oid)
  {
    var idx := FindIndex(id);
    var e := entries[idx];
    var newEntry := Entry(e.id, e.invocations, e.successes, e.tier, true);
    var oldEntries := entries;
    entries := entries[..idx] + [newEntry] + entries[idx+1..];
    
    assert entries[idx].id == id;
    assert entries[idx].archived == true;
    
    forall i | 0 <= i < |entries| && entries[i].id != id
      ensures FindIndexPure(entries[i].id, oldEntries) >= 0 &&
              entries[i] == oldEntries[FindIndexPure(entries[i].id, oldEntries)]
    {
      if i < idx {
        assert entries[i] == oldEntries[i];
        assert oldEntries[i].id == entries[i].id;
        assert oldEntries[i].id != id;
        FindIndexPureCorrect(entries[i].id, oldEntries, i);
        assert FindIndexPure(entries[i].id, oldEntries) == i;
      } else if i > idx {
        assert entries[i] == oldEntries[i];
        assert oldEntries[i].id == entries[i].id;
        assert oldEntries[i].id != id;
        FindIndexPureCorrect(entries[i].id, oldEntries, i);
        assert FindIndexPure(entries[i].id, oldEntries) == i;
      }
    }
    
    forall oid | exists j :: 0 <= j < |oldEntries| && oldEntries[j].id == oid
      ensures exists j :: 0 <= j < |entries| && entries[j].id == oid
    {
      var j :| 0 <= j < |oldEntries| && oldEntries[j].id == oid;
      if j == idx {
        assert entries[idx].id == id;
        assert oid == id;
        assert entries[idx].id == oid;
      } else {
        assert entries[j] == oldEntries[j];
        assert entries[j].id == oid;
      }
    }
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
    ensures found <==> exists i :: 0 <= i < |entries| && entries[i].id == id
  {
    var idx := FindIndex(id);
    found := idx >= 0;
  }
}

method Main()
{
  var reg := new ToolRegistry();

  // Upsert two tools
  reg.Upsert("tool1", 0);
  assert exists i :: 0 <= i < |reg.entries| && reg.entries[i].id == "tool1";

  reg.Upsert("tool2", 1);
  assert exists i :: 0 <= i < |reg.entries| && reg.entries[i].id == "tool2";

  // RecordUsage: invocations increment, collection size unchanged
  reg.RecordUsage("tool1", true);
  reg.RecordUsage("tool1", false);

  // Promote: tier advances one step
  reg.Promote("tool1");

  // Archive: entry remains, status changes
  reg.Archive("tool2");

  // Read-only operations
  var c := reg.Count();
  assert c == |reg.entries|;

  var found := reg.Lookup("tool1");
  var notFound := reg.Lookup("tool3");
  assert !notFound;
}