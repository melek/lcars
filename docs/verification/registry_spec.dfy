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

  method FindIndex(id: string) returns (idx: int)
    requires Valid()
    ensures -1 <= idx < |entries|
    ensures idx == -1 ==> forall i :: 0 <= i < |entries| ==> entries[i].id != id
    ensures idx >= 0 ==> entries[idx].id == id
  {
    idx := -1;
    var i := 0;
    while i < |entries|
      invariant 0 <= i <= |entries|
      invariant idx == -1 ==> forall k :: 0 <= k < i ==> entries[k].id != id
      invariant idx >= 0 ==> idx < |entries| && entries[idx].id == id
      decreases |entries| - i
    {
      if entries[i].id == id {
        idx := i;
        return;
      }
      i := i + 1;
    }
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
  {
    var idx := FindIndex(id);
    if idx >= 0 {
      var e := entries[idx];
      var newEntry := Entry(e.id, e.invocations, e.successes, tier, e.archived);
      entries := entries[..idx] + [newEntry] + entries[idx+1..];
    } else {
      var newEntry := Entry(id, 0, 0, tier, false);
      entries := entries + [newEntry];
    }
  }

  method RecordUsage(id: string, success: bool)
    requires Valid()
    requires exists i :: 0 <= i < |entries| && entries[i].id == id
    modifies this
    ensures Valid()
    ensures |entries| == old(|entries|)
    ensures exists i :: 0 <= i < |entries| && entries[i].id == id &&
              entries[i].invocations == old(entries)[FindIndexPure(id, old(entries))].invocations + 1 &&
              (success ==> entries[i].successes == old(entries)[FindIndexPure(id, old(entries))].successes + 1) &&
              (!success ==> entries[i].successes == old(entries)[FindIndexPure(id, old(entries))].successes)
    ensures forall i :: 0 <= i < |entries| && entries[i].id != id ==>
              entries[i] == old(entries)[FindIndexPure(entries[i].id, old(entries))]
  {
    var idx := FindIndex(id);
    var e := entries[idx];
    var newSuccesses := if success then e.successes + 1 else e.successes;
    var newEntry := Entry(e.id, e.invocations + 1, newSuccesses, e.tier, e.archived);
    entries := entries[..idx] + [newEntry] + entries[idx+1..];
  }

  method Promote(id: string)
    requires Valid()
    requires exists i :: 0 <= i < |entries| && entries[i].id == id
    modifies this
    ensures Valid()
    ensures |entries| == old(|entries|)
    ensures exists i :: 0 <= i < |entries| && entries[i].id == id &&
              (old(entries)[FindIndexPure(id, old(entries))].tier == 0 ==> entries[i].tier == 1) &&
              (old(entries)[FindIndexPure(id, old(entries))].tier == 1 ==> entries[i].tier == 2) &&
              (old(entries)[FindIndexPure(id, old(entries))].tier == 2 ==> entries[i].tier == 2) &&
              entries[i].tier <= old(entries)[FindIndexPure(id, old(entries))].tier + 1 &&
              entries[i].tier <= 2
    ensures forall i :: 0 <= i < |entries| && entries[i].id != id ==>
              entries[i] == old(entries)[FindIndexPure(entries[i].id, old(entries))]
  {
    var idx := FindIndex(id);
    var e := entries[idx];
    var newTier := if e.tier < 2 then e.tier + 1 else e.tier;
    var newEntry := Entry(e.id, e.invocations, e.successes, newTier, e.archived);
    entries := entries[..idx] + [newEntry] + entries[idx+1..];
  }

  method Archive(id: string)
    requires Valid()
    requires exists i :: 0 <= i < |entries| && entries[i].id == id
    modifies this
    ensures Valid()
    ensures |entries| == old(|entries|)
    ensures exists i :: 0 <= i < |entries| && entries[i].id == id && entries[i].archived == true
    ensures forall i :: 0 <= i < |entries| && entries[i].id != id ==>
              entries[i] == old(entries)[FindIndexPure(entries[i].id, old(entries))]
  {
    var idx := FindIndex(id);
    var e := entries[idx];
    var newEntry := Entry(e.id, e.invocations, e.successes, e.tier, true);
    entries := entries[..idx] + [newEntry] + entries[idx+1..];
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

  static function FindIndexPure(id: string, s: seq<Entry>): int
  {
    if |s| == 0 then -1
    else if s[0].id == id then 0
    else
      var rest := FindIndexPure(id, s[1..]);
      if rest == -1 then -1 else rest + 1
  }
}

method Main()
{
  var reg := new ToolRegistry();
  reg.Upsert("tool1", 0);
  reg.Upsert("tool2", 1);
  reg.RecordUsage("tool1", true);
  reg.RecordUsage("tool1", false);
  reg.Promote("tool1");
  reg.Archive("tool2");
  var c := reg.Count();
  var found := reg.Lookup("tool1");
  var notFound := reg.Lookup("tool3");
}