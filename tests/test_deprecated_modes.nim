import
  helpers,
  std/[json, os, strutils, unittest],
  ctf/[replay_runtime, replays, sim],
  shell/[episode, runtime_boot]

const
  ReplayFixture = GameDir / "tests" / "replays" / "ctf.bitreplay"
  ManifestName = GameDir / "coworld_manifest_paintbot_royal.json"

proc expectDeprecatedRefusal(config: GameConfig, expectedTriggers: string) =
  var caught = false
  try:
    config.checkDeprecatedMode()
  except CtfError as error:
    caught = true
    check "deprecated since 0.7.253" in error.msg
    check "allowDeprecatedModes" in error.msg
    check "[" & expectedTriggers & "]" in error.msg
  check caught

const ArchiveName = GameDir / "deprecated_variants_paintbot.json"

proc manifestVariantConfig(variantId: string): JsonNode =
  ## Published manifest first, then the classic archive: since the
  ## paintbot-royal split the classic variants are fixtures, not published.
  for name in [ManifestName, ArchiveName]:
    for variant in parseFile(name)["variants"]:
      if variant["id"].getStr() == variantId:
        return variant["game_config"]
  raise newException(ValueError, "missing manifest variant " & variantId)

suite "deprecated live-mode boot seam":
  test "classic live config refuses unless the override is set":
    var classic = defaultGameConfig()
    classic.numAgents = 16
    classic.brMode = false
    classic.expectDeprecatedRefusal("classic")

    classic.allowDeprecatedModes = true
    classic.checkDeprecatedMode()

  test "each trigger is named and multiple triggers stay ordered":
    block:
      var config = defaultGameConfig()
      config.brMode = true
      config.season2Shell = false
      config.expectDeprecatedRefusal("season1Shell")
    block:
      var config = defaultGameConfig()
      config.brMode = true
      config.loadout = LoadoutPaintball
      config.expectDeprecatedRefusal("paintball")
    block:
      var config = defaultGameConfig()
      config.brMode = true
      config.floorPaint = true
      config.expectDeprecatedRefusal("paintball")
    block:
      var config = defaultGameConfig()
      config.brMode = true
      config.paintBuff = true
      config.expectDeprecatedRefusal("paintball")
    block:
      var config = defaultGameConfig()
      config.brMode = true
      config.hill = true
      config.expectDeprecatedRefusal("paintball")
    block:
      var config = defaultGameConfig()
      config.brMode = true
      config.numAgents = 16
      config.cogsPerTeam = 4
      config.expectDeprecatedRefusal("squadMode")
    block:
      var config = defaultGameConfig()
      config.brMode = false
      config.season2Shell = false
      config.loadout = LoadoutPaintball
      config.numAgents = 16
      config.cogsPerTeam = 4
      config.expectDeprecatedRefusal(
        "classic, season1Shell, paintball, squadMode")

  test "season 2 battle royale shape does not refuse":
    var config = defaultGameConfig()
    config.brMode = true
    check config.season2Shell
    check config.loadout == LoadoutCtf
    check not config.floorPaint
    check not config.paintBuff
    check not config.hill
    check config.cogsPerTeam == 1
    config.checkDeprecatedMode()

  test "landed battle-royale-s2 manifest variant matches the supported shape":
    var config = defaultGameConfig()
    config.update($manifestVariantConfig("battle-royale-s2"))
    config.checkDeprecatedMode()

  test "battle-royale-s2 manifest entry carries no override -- the gate stays live for it":
    ## Elite/Campaign's fix is scoped to the classic templates below; this
    ## guards against "fix" meaning "defeat the gate for everyone".
    let s2GameConfig = manifestVariantConfig("battle-royale-s2")
    check not s2GameConfig.hasKey("allowDeprecatedModes")

  test "every archived classic template refuses without the override and boots with it":
    ## SPLIT (2026-09-21): this repo publishes the paintbot-royal Coworld,
    ## whose manifest is the Season 2 family only. The classic templates
    ## (2v2 / 4ffa / 4ffa8 / default / 1v1 / ctf-default / ctf-1v1 /
    ## paintball / battle-royale) are engine fixtures here, archived as
    ## shipped in deprecated_variants_paintbot.json WITHOUT the override --
    ## coworld-ctf is where they are published with allowDeprecatedModes
    ## and where "Elite/Campaign boot" is guarded. What this repo owns is
    ## the seam itself: every archived classic template hits
    ## checkDeprecatedMode's CtfError at live boot as shipped, and boots
    ## once the override is applied, so a future engine change cannot
    ## silently defeat the gate (or silently break the classic modes).
    for variantId in ["2v2", "4ffa", "4ffa8", "default", "1v1",
        "ctf-default", "ctf-1v1", "paintball", "battle-royale"]:
      let gameConfig = manifestVariantConfig(variantId)
      check not gameConfig.hasKey("allowDeprecatedModes")
      var refusing = defaultGameConfig()
      refusing.update($gameConfig)
      check not refusing.allowDeprecatedModes
      # Which trigger(s) fire differs per template ("classic" for the
      # 2v2/ctf family, "season1Shell" for the archived battle-royale,
      # "paintball" for the paintball loadout); the seam property is only
      # that the gate refuses and names the override.
      var refused = false
      try:
        refusing.checkDeprecatedMode()
      except CtfError as error:
        refused = true
        check "allowDeprecatedModes" in error.msg
      check refused
      var overridden = copy(gameConfig)
      overridden["allowDeprecatedModes"] = %true
      var config = defaultGameConfig()
      config.update($overridden)
      check config.allowDeprecatedModes
      config.checkDeprecatedMode()

  test "CTF-branded classic templates boot with the override too -- only the CTF league stays gone":
    ## Kept as a named regression guard on these three ids (see the
    ## comprehensive test above and the 2026-09-02 owner correction in
    ## coworld-ctf: CTF is a fine game mode; only the CTF *league* is
    ## retired). Same seam, same shape: refuse as archived, boot overridden.
    for variantId in ["ctf-default", "ctf-1v1", "default"]:
      var overridden = copy(manifestVariantConfig(variantId))
      overridden["allowDeprecatedModes"] = %true
      var config = defaultGameConfig()
      config.update($overridden)
      check config.allowDeprecatedModes
      config.checkDeprecatedMode()

  test "legacy replay fixture drives the real replay path without override":
    ## The fixture is cut by tools/record_fixture.sh, which boots the live
    ## server with the legacy override (a classic game refuses to boot
    ## without it since 2653b7cc) and echoShellKeys records that override in
    ## the header. The property under test is the REPLAY path's: the same
    ## classic config is refused at live boot without the override, yet the
    ## recording plays back regardless of it — playback never consults the
    ## seam. So the refusal is checked on the header minus the override,
    ## and playback is checked on the header as recorded.
    let data = loadReplay(ReplayFixture)
    var recorded = parseJson(data.configJson)
    if recorded.hasKey("allowDeprecatedModes"):
      recorded.delete("allowDeprecatedModes")
    var replayConfig = defaultGameConfig()
    replayConfig.update($recorded)
    replayConfig.expectDeprecatedRefusal("classic")

    let previousDir = getCurrentDir()
    setCurrentDir(GameDir)
    try:
      let runtime = initReplayRuntime(
        data, mismatchQuit = true, gameEventLoggingEnabled = false)
      check runtime.sim.tickCount >= 0
      check not runtime.config.brMode          # it really is the classic game
    finally:
      setCurrentDir(previousDir)

  test "echo rules for the live legacy override":
    var config = defaultGameConfig()
    config.update($ %*{"allowDeprecatedModes": true})
    let node = parseJson(config.configJson())
    check not node.hasKey("season2Shell")
    check node["allowDeprecatedModes"].getBool()

  test "runtime-stub binary refuses live play seats but not non-play configs":
    var noPlay = defaultGameConfig()
    noPlay.brMode = true
    noPlay.checkPlayRuntimeAvailable()

    var playSeat = defaultGameConfig()
    playSeat.update($ %*{
      "brMode": true,
      "minPlayers": 2,
      "closedRoster": true,
      "players": [{"name": "alpha"}, {"name": "beta"}],
      "tokens": ["t-alpha", "t-beta"],
      "slots": [{"team": "red", "control": "play"}, {"team": "blue"}]
    })
    when ShellRuntimeAvailable:
      playSeat.checkPlayRuntimeAvailable()
    else:
      var caught = false
      try:
        playSeat.checkPlayRuntimeAvailable()
      except CtfError as error:
        caught = true
        check "this binary was built without the play runtime" in error.msg
      check caught

  test "runtime-stub refusal exempts replay by caller placement":
    let data = loadReplay(ReplayFixture)
    let previousDir = getCurrentDir()
    setCurrentDir(GameDir)
    try:
      let runtime = initReplayRuntime(
        data, mismatchQuit = true, gameEventLoggingEnabled = false)
      check runtime.sim.tickCount >= 0
    finally:
      setCurrentDir(previousDir)
