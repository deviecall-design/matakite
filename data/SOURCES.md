# Sources for the 2026 All Blacks record

Checked on 28 September 2026, again on 7 October 2026 for the player dossier, again on 12 October 2026 after Eden Park, and again on 19 October 2026 (Sydney) after the Sydney Test. The Rugby Database New Zealand games list and the All Test Match list both now include 17 October, Australia 21–43 All Blacks at Accor Stadium, crowd 73,399, kick-off 3:45pm, game 30266. The ESPN results list, fetched the same day, shows Australia 21–43 New Zealand at Accor Stadium. Sky Sports shows the same final score.

The player dossier is `player-dossier.html`. It reads `data/player-dossier-2026.json` and this season file. Every score on the page is New Zealand first, then the opponent. Rugby Database lists the home side first, so away results are flipped to keep New Zealand first.

The page reads `data/all-blacks-2026.json`. `data/compute_season_stats.py` adds the season totals and stops if a Test score sheet does not add up to the final score. The page does the same sum again when it loads.

## How the two main sources were used

Primary source for played results, venues and crowds: [Rugby Database, New Zealand games list](https://www.rugbydatabase.com.au/team/games-list.php?teamId=3). The list is embedded in the page. A plain fetch without a browser Accept header was refused (HTTP 406). With a normal browser header the list loaded. Each played game below links to its Rugby Database game page.

Cross-check for Tests: [ESPN New Zealand team page](https://www.espn.com.au/rugby/team/_/id/8/new-zealand) and its [2026 results list](https://www.espn.com.au/rugby/results/_/team/8/). The ESPN website returned the pages (HTTP 200) with a normal browser user agent. An earlier audit found the ESPN site API returned HTTP 403 from this machine. That API was not used. The HTML pages were not blocked.

ESPN's results list, when it was read in September, had the seven Tests through Baltimore. Scores agreed with Rugby Database on all seven. On 12 October a direct fetch of that results page was blocked by a bot check. The Eden Park match page was read from an index and agrees at 50–19. The four tour matches were checked against the [Wikipedia tour page](https://en.wikipedia.org/wiki/2026_New_Zealand_rugby_union_tour_of_South_Africa).

These ESPN paths did not give the New Zealand upcoming list, so they were not used as a fixture source:

- `https://www.espn.com.au/rugby/fixtures/_/team/8/` returned a generic rugby fixtures page, not the All Blacks list.
- `https://www.espn.com.au/rugby/team/fixtures/_/id/8/` and `https://www.espn.com.au/rugby/team/squad/_/id/8/nzl` returned HTTP 404.

Upcoming fixtures stay on allblacks.com. On 19 Oct 2026 (Sydney) the Rugby Database list's newest All Blacks game was Sydney. The November Tests were not on it.

## Played Tests

| Date | Opponent | Venue (Rugby Database) | Crowd | Result | Rugby Database | ESPN cross-check |
|---|---|---|---|---|---|---|
| 4 Jul 2026 | France | One New Zealand Stadium | 30,000 | Won 34–32 | [game 29341](https://www.rugbydatabase.com.au/game.php?gameId=29341) | [match 603975](https://www.espn.com.au/rugby/match/_/gameId/603975/league/289234) |
| 11 Jul 2026 | Italy | Hnry Stadium | 33,087 | Won 47–17 | [game 29347](https://www.rugbydatabase.com.au/game.php?gameId=29347) | [match 603981](https://www.espn.com.au/rugby/match/_/gameId/603981/league/289234) |
| 18 Jul 2026 | Ireland | Eden Park | 48,153 | Won 40–21 | [game 29353](https://www.rugbydatabase.com.au/game.php?gameId=29353) | [match 603987](https://www.espn.com.au/rugby/match/_/gameId/603987/league/289234) |
| 22 Aug 2026 | South Africa | Emirates Airline Park | 60,592 | Won 33–16 | [game 29379](https://www.rugbydatabase.com.au/game.php?gameId=29379) | [match 603247](https://www.espn.com.au/rugby/match/_/gameId/603247/league/289234) |
| 29 Aug 2026 | South Africa | Cape Town Stadium | 56,589 | Lost 26–33 | [game 29381](https://www.rugbydatabase.com.au/game.php?gameId=29381) | [match 603248](https://www.espn.com.au/rugby/match/_/gameId/603248/league/289234) |
| 5 Sep 2026 | South Africa | First National Bank Stadium | 85,967 | Lost 24–29 | [game 29382](https://www.rugbydatabase.com.au/game.php?gameId=29382) | [match 603249](https://www.espn.com.au/rugby/match/_/gameId/603249/league/289234) |
| 12 Sep 2026 | South Africa | M&T Bank Stadium | 68,173 | Lost 28–43 | [game 29383](https://www.rugbydatabase.com.au/game.php?gameId=29383) | [match 603250](https://www.espn.com.au/rugby/match/_/gameId/603250/league/289234) |
| 10 Oct 2026 | Australia | Eden Park | 46,352 | Won 50–19 | [game 30265](https://www.rugbydatabase.com.au/game.php?gameId=30265) | [match 603463](https://www.espn.com.au/rugby/match/_/gameId/603463/league/289234/australia-new-zealand) |
| 17 Oct 2026 | Australia | Accor Stadium | 73,399 | Won 43–21 | [game 30266](https://www.rugbydatabase.com.au/game.php?gameId=30266) | [ESPN results list](https://www.espn.com.au/rugby/results/_/team/8/), Sat, Oct 17, Australia 21–43 New Zealand, Accor Stadium. Fetched 19 Oct 2026 (Sydney). |

Try scorers for those Tests come from match reports, not from Rugby Database (its game pages do not list a full try sequence):

- France: [All Blacks](https://www.allblacks.com/news/all-blacks/all-blacks-edge-france-in-christchurch-thriller-to-open-2026), [BBC Sport](https://www.bbc.com/sport/rugby-union/articles/c5yze25d46do), [NZ Herald](https://www.nzherald.co.nz/sport/rugby/all-blacks/all-blacks-v-france-result-dave-rennie-era-begins-with-nail-biting-win-in-christchurch/XMVJFMPVYVAONARUXCGHTFY6NY/).
- Italy: [All Blacks](https://www.allblacks.com/news/all-blacks/will-jordan-breaks-all-blacks-try-scoring-record-in-47-17-win-over-italy), [Sky Sports](https://www.skysports.com/rugby-union/new-zealand-vs-italy/111670), [BBC Sport](https://www.bbc.com/sport/rugby-union/articles/c24y0lpj227o).
- Ireland: [All Blacks](https://www.allblacks.com/news/all-blacks/match-report-all-blacks-vs-ireland-nations-championship), [BBC Sport](https://www.bbc.com/sport/rugby-union/articles/c4gk5exp8eko).
- Emirates Airline Park: [All Blacks](https://www.allblacks.com/news/all-blacks/match-report-all-blacks-v-springboks-first-test-rugby-s-greatest-rivalry), [Sky Sports](https://www.skysports.com/rugby-union/news/12321/13575921/south-africa-vs-new-zealand-all-blacks-emerge-worthy-winners-as-they-outscore-springboks-in-first-test-upset).
- Cape Town Stadium: [Sky Sports](https://www.skysports.com/rugby-union/south-africa-vs-new-zealand/111659), [BBC Sport](https://www.bbc.co.uk/sport/rugby-union/match/EVP5649499), [AP](https://apnews.com/article/south-africa-springboks-all-blacks-2nd-test-b996752150947b828d8c0aff1adda7f0).
- First National Bank Stadium: [BBC Sport](https://www.bbc.com/sport/rugby-union/articles/c7830m55lklo), [Sky Sports](https://www.skysports.com/rugby-union/news/13582037/south-africa-29-24-new-zealand-springboks-edge-thriller-to-take-2-1-series-lead-in-soweto).
- Baltimore: [BBC Sport](https://www.bbc.com/sport/rugby-union/articles/c07lmxpmvr9o), [Sky Sports](https://www.skysports.com/rugby-union/news/12321/13584821/south-africa-vs-new-zealand-springboks-show-steel-to-secure-43-28-victory-and-3-1-series-win-against-all-blacks), [All Blacks](https://www.allblacks.com/news/all-blacks/all-blacks-return-to-hilux-npc-as-focus-shifts-to-bledisloe).
- Eden Park: [BBC Sport](https://www.bbc.co.uk/sport/rugby-union/articles/c9zrdl4028mko), [Sky Sports](https://www.skysports.com/rugby-union/news/13596830/new-zealand-50-19-australia-all-blacks-power-to-eden-park-victory-to-retain-bledisloe-cup-for-24th-year), [ESPN](https://www.espn.com/rugby/story/_/id/50145167/bledisloe-cup-australia-new-zealand-all-blacks-punish-wayward-wallabies-second-half-blowout-eden-park), [1News](https://www.1news.co.nz/2026/10/10/all-blacks-regain-confidence-in-bledisloe-cup-rout/). Rugby Database's own game page also lists the try scorers and the kickers, and they match those reports.
- Sydney: Rugby Database game 30266 lists the tries and kicks. New Zealand: Josh Moorby 2, Beauden Barrett 2, Peter Lakai, Rieko Ioane, Wallace Sititi, Damian McKenzie 4 conversions and no penalties. Australia: Jeremy Williams, Tom Wright, Filipo Daugunu, Ryan Lonergan 2 conversions, Declan Meredith 1 conversion. No penalty tries. That is 43 and 21. [Sky Sports](https://www.skysports.com/rugby-union/australia-vs-new-zealand/111860) lists the same try scorers and the same kicks. [Rugby Australia](https://www.rugby.com.au/news/all-blacks-complete-bledisloe-cup-sweep-with-sydney-victory-over-wallabies-20261017) lists the same scorers. Half-time is not on the Rugby Database page. Rugby Australia's report says 36–7 at the break. Sky's listed minutes do not add to 36 in the first half, so the page does not show a half-time.

Series result against South Africa: South Africa won 3–1. The Bledisloe Cup was retained at Eden Park. Sydney was won 43–21. Rugby Australia calls that a clean sweep. This page does not add a year-count for the cup.

Test record from the score sheets: played 9, won 6, lost 3, drawn 0, points for 325, points against 231, tries for 49, tries against 29. Will Jordan has 11 tries and 55 points, the most of both on those sheets. He did not score in Sydney.

## Tour matches (not Tests)

These four are on the Rugby Database list under "All Blacks in South Africa & United States - 2026". They are not on the ESPN New Zealand results list. Scores match Wikipedia. No try scorers are shown.

| Date | Opponent | Venue | Crowd | Result | Rugby Database |
|---|---|---|---|---|---|
| 7 Aug 2026 | Stormers | Cape Town Stadium | 47,130 | Won 38–21 | [game 29376](https://www.rugbydatabase.com.au/game.php?gameId=29376) |
| 11 Aug 2026 | Sharks | Kings Park Stadium | 14,759 | Won 54–0 | [game 29377](https://www.rugbydatabase.com.au/game.php?gameId=29377) |
| 15 Aug 2026 | Bulls | Loftus Versfeld Stadium | 30,930 | Won 50–19 | [game 29378](https://www.rugbydatabase.com.au/game.php?gameId=29378) |
| 25 Aug 2026 | Lions | Emirates Airline Park | 15,956 | Won 41–35 | [game 29380](https://www.rugbydatabase.com.au/game.php?gameId=29380) |

All games on that list: played 13, won 10, lost 3, drawn 0, points for 508, points against 306. Try totals stay on the nine Tests. Sydney is the thirteenth game.

## Where the two sources do not use the same words

Scores agree on every Test both lists carry. The rows below are names, clocks, and one year-count. None of them is a different score.

| Game | Field | Rugby Database | ESPN |
|---|---|---|---|
| 4 Jul, France | Venue name | One New Zealand Stadium | One NZ Stadium, Christchurch |
| 22 Aug, South Africa | Venue name | Emirates Airline Park | Ellis Park, Johannesburg |
| 29 Aug, South Africa | Venue name | Cape Town Stadium | DHL Stadium, Cape Town |
| 5 Sep, South Africa | Venue name | First National Bank Stadium | FNB Stadium, Johannesburg |
| 12 Sep, South Africa | Date label | Sat 12th Sep 2026, 12:00pm | Results list: Sat, Sep 12. Match summary title: 13 Sep 2026. Game info: 7:00 AM, September 13, 2026 |
| 10 Oct, Australia | Kick-off clock | Sat 10th Oct 2026, 7:10pm | Game info: 5:10 PM, October 10, 2026 |
| 10 Oct, Australia | Bledisloe year count | Not a Rugby Database field. allblacks.com says held since 2003 | ESPN story: a 24-year grip, since 2003. Sky: a 24th year. BBC: a 23rd straight year |
| 10 Oct, Australia | Bench surname | Rieko Ioane | Not an ESPN field. BBC's reserve list prints Loane. The All Blacks team page says Rieko Ioane |

The page uses the Rugby Database venue names. The Baltimore date on the page is Saturday 12 September, which is what BBC and Sky reported in Baltimore. The 13 September clock is the ESPN Australia edition, not a second match. Rugby Database's own stored timestamp for that game is midnight UTC on 12 September, which does not match its "12:00pm" label. The date used is still Saturday 12 September.

The Eden Park kick-off on the page is 7.10pm, from Rugby Database and allblacks.com. The 5:10 PM label is the ESPN Australia clock. BBC's "Loane" is treated as Rieko Ioane. The page does not choose between a 23rd and a 24th year of holding the Bledisloe Cup.

ESPN match pages for the earlier Tests store attendance as 0. That is missing data, not a crowd of zero, so it is not treated as a disagreement. Baltimore's 68,173 also matches [BBC Sport](https://www.bbc.com/sport/rugby-union/articles/c07lmxpmvr9o). Eden Park's 46,352 is on Rugby Database, and the ESPN story uses the same figure. The other crowds are Rugby Database only.

A direct fetch of the ESPN Australia HTML on 12 October was blocked by a bot check. The match page text was read from an index. It shows Eden Park, 10 October 2026, and a commentary that finishes 50–19. The [ESPN story](https://www.espn.com/rugby/story/_/id/50145167/bledisloe-cup-australia-new-zealand-all-blacks-punish-wayward-wallabies-second-half-blowout-eden-park) states the same score and a 17–14 half-time.

## Still to be played

Sydney has been played. These were not on the Rugby Database games list on 19 Oct 2026 (Sydney). The next one on the season file is Scotland.

| Date on the page | Opponent | Venue | Note | Source |
|---|---|---|---|---|
| 7 Nov 2026 local | Scotland | Murrayfield, Edinburgh | allblacks.com heads this as Sunday 8 November, 3.10am NZDT / 2.10pm GMT | [All Blacks](https://www.allblacks.com/news/all-blacks/the-nations-championship-explained) |
| 14 Nov 2026 local | Wales | Principality Stadium, Cardiff | Sunday 15 November, 3.10am NZDT / 2.10pm GMT on allblacks.com | [All Blacks](https://www.allblacks.com/news/all-blacks/the-nations-championship-explained) |
| 21 Nov 2026 local | England | Twickenham Stadium, London | Sunday 22 November, 3.10am NZDT / 2.10pm GMT on allblacks.com | [All Blacks](https://www.allblacks.com/news/all-blacks/the-nations-championship-explained) |

2.10pm GMT is the previous calendar day in Britain from a 3.10am New Zealand clock. The page uses the local Saturday date and says so.

## Coach, captain, and the Bledisloe preview

- Head coach Dave Rennie, appointed 4 March 2026: [New Zealand Rugby](https://www.nzrugby.co.nz/news-and-events/latest-news/new-zealand-rugby-appoints-dave-rennie-as-all-blacks-head-coach).
- Scott Robertson's departure, January 2026: [All Blacks](https://www.allblacks.com/news/scott-robertson-departs-as-head-coach-of-the-all-blacks).
- Ardie Savea named captain on the Italy team sheet: [All Blacks](https://www.allblacks.com/news/all-blacks/all-blacks-team-named-to-play-italy-in-wellington).
- Codie Taylor captained Baltimore. Savea and Jacobson to miss the Bledisloe squad being planned. Cup held since 2003. Injury list as at 21 September 2026: [All Blacks](https://www.allblacks.com/news/all-blacks/all-blacks-return-to-hilux-npc-as-focus-shifts-to-bledisloe).
- Savea surgery confirmed: [RNZ](https://www.rnz.co.nz/news/sport/1496364/all-blacks-captain-ardie-savea-faces-lengthy-spell-on-sideline-after-surgery-confirmed).
- Australia 42–38 South Africa, Perth, 27 September 2026: [BBC Sport](https://www.bbc.co.uk/sport/rugby-union/articles/cx05r4gg209ro), [RNZ](https://www.rnz.co.nz/news/sport/1621006/wallabies-hold-on-with-11-men-to-beat-springboks).

## Game-plan quotes

Compiled from public reporting on 28 Sep 2026. This is not an AI analysis.

- Rennie after Baltimore, on the high ball, the set piece that night, discipline, Beauden Barrett, and "tracking in the right direction": [Planet Rugby, 13 Sep 2026](https://www.planetrugby.com/news/why-dave-rennie-believes-all-blacks-are-tracking-in-right-direction-despite-3-1-series-defeat-to-the-springboks-and-the-dumb-stuff-he-wants-to-get-out-of-the-game).
- Series review, attack, scrum penalties, lineout, high ball, and wingers in midfield: [ESPN, Liam Napier, 20 Sep 2026](https://www.espn.com/rugby/story/_/id/49995477/all-blacks-rgr-review-working-not-lies-ahead).
- All Blacks site on the series, the bench, and the Bledisloe: [All Blacks](https://www.allblacks.com/news/all-blacks/all-blacks-return-to-hilux-npc-as-focus-shifts-to-bledisloe).
- Rennie before July, on counter-attack: [SABC Sport](https://www.sabcsport.com/rugby/news/dave-rennie-outlines-what-he-s-looking-for-in-new-all-blacks), [RugbyPass](https://www.rugbypass.com/news/stephen-donald-unpacks-what-dave-rennies-comments-reveal-about-his-game-plan/).

## Eden Park, checked 12 October 2026

Result, venue, crowd and kick-off: Rugby Database game 30265. Score cross-check: ESPN match 603463 and the ESPN story. Half-time 17–14: BBC's scoreline shows 17 and 14, Sky says three points ahead at the break after two tries each, 1News says 17–14, and the ESPN story says 17–14.

Tries and kicks, all one each unless noted: Peter Lakai, Tupou Vaa'i, Cam Roigard, Codie Taylor, Leroy Carter, Josh Moorby, Will Jordan. Damian McKenzie six conversions and one penalty. Australia: Tom Wright, Harry Wilson, Josh Nasser. Ryan Lonergan two conversions and no penalties. That is 50 and 19. Rugby Database's scoring table matches.

Match-day 23: [All Blacks](https://www.allblacks.com/news/all-blacks/all-blacks-team-named-for-first-bledisloe-cup-test), the same 23 on [RNZ](https://www.rnz.co.nz/news/sport/1791509/all-blacks-damian-mckenzie-at-no-10-as-beauden-barrett-comes-back-in-from-the-cold), and the Rugby Database game page. Codie Taylor captained. Damian McKenzie started at first five. Beauden Barrett started at fullback.

Unavailable for that 23: Richie Mo'unga (calf), Fehi Fineanganofo (concussion and a hamstring). The [selection story](https://www.allblacks.com/news/all-blacks/why-this-was-rennie-s-hardest-all-blacks-team-to-pick-yet) says Mo'unga is also likely to miss Sydney.

Injuries after the match, 11 October: [All Blacks](https://www.allblacks.com/news/all-blacks/all-blacks-injury-update-x2281) and [RNZ](https://www.rnz.co.nz/news/sport/1837508/four-all-blacks-ruled-out-of-sydney-trip-fan-favourite-du-plessis-kirifi-included). Leroy Carter, high ankle sprain. Asafo Aumua and Anton Segner, failed a second head-injury assessment, minimum 12 days. Ethan Blackadder, calf in the warm-up. Replacements: Anton Lienert-Brown, George Bell, Du'Plessis Kirifi, Jamie Hannah. RNZ says Scott Barrett passed a second assessment and travelled. 1News, on the night, said he had failed the first one. Those two reports are the same episode, a day apart.

Coach's words used on the page are from [1News](https://www.1news.co.nz/2026/10/10/all-blacks-regain-confidence-in-bledisloe-cup-rout/) and the [ESPN story](https://www.espn.com/rugby/story/_/id/50145167/bledisloe-cup-australia-new-zealand-all-blacks-punish-wayward-wallabies-second-half-blowout-eden-park). 1News also said Will Jordan's career try tally moved to 56, and gave tackle counts. Those are not re-counted, and they are not on the page as facts.

The All Blacks injury update spells the new loose forward Du'plessis. RNZ spells Du'Plessis Kirifi. The page uses the RNZ spelling.

## Player dossier, checked 7 October 2026, then Eden Park on 12 October 2026

The page is for coaches. It lists the 29 September Bledisloe squad, the eight players left out injured, and Sam Darry, who RNZ said missed the cut and who has no injury on that list. Each Test row is a published match-day 23. It is not a minute count. Points and tries are added from the seven Test score sheets in `data/all-blacks-2026.json`. Tour matches stay off the player charts because this file has no tour try list.

Squad and injuries:

- Squad, captain Codie Taylor, and the unavailable list: [RNZ, 29 Sep 2026](https://www.rnz.co.nz/news/sport/1649070/all-blacks-named-for-bledisloe-codie-taylor-captain-scott-barrett-and-shannon-frizell-back), [Super Rugby](https://super.rugby/therugbychampionship/news/all-blacks-squad-names-for-two-match-bledilsoe-cup-series/), [ESPN](https://www.espn.com.sg/rugby/story/_/id/50056066/bledisloe-cup-shannon-frizell-back-all-blacks-lose-star-10-injury).
- Injury windows as at 21 September: [All Blacks](https://www.allblacks.com/news/all-blacks/all-blacks-return-to-hilux-npc-as-focus-shifts-to-bledisloe).
- Savea's operation and a Super Rugby 2027 return, in Dave Rennie's words, plus the report that Ruben Love is out for the rest of the season: [Planet Rugby, 4 Oct 2026](https://www.planetrugby.com/news/all-blacks-dave-rennie-why-ardie-saveas-might-be-a-good-thing).
- Savea surgery confirmed earlier: [RNZ](https://www.rnz.co.nz/news/sport/1496364/all-blacks-captain-ardie-savea-faces-lengthy-spell-on-sideline-after-surgery-confirmed).

Match-day 23s:

| Test | Sheet |
|---|---|
| France, 4 Jul | [All Blacks](https://www.allblacks.com/news/all-blacks/all-blacks-team-to-play-france-in-christchurch) |
| Italy, 11 Jul | [All Blacks](https://www.allblacks.com/news/all-blacks/all-blacks-team-named-to-play-italy-in-wellington) |
| Ireland, 18 Jul | [All Blacks](https://www.allblacks.com/news/all-blacks/all-blacks-team-named-to-play-ireland-in-auckland) |
| South Africa, 22 Aug | [1News](https://www.1news.co.nz/2026/08/20/key-all-blacks-trio-named-to-start-first-test-against-boks/), late change [SABC Sport](https://www.sabcsport.com/rugby/news/all-blacks-forced-into-late-change-for-springboks-clash-at-ellis-park) |
| South Africa, 29 Aug | [Super Rugby](https://super.rugby/therugbychampionship/news/all-blacks-team-announced-for-second-rgr-test/), [BBC Sport line-up](https://www.bbc.com/sport/rugby-union/articles/c1mvred1l7do) |
| South Africa, 5 Sep | [All Blacks](https://www.allblacks.com/news/all-blacks/all-blacks-team-to-play-south-africa-in-third-test-in-johannesburg) |
| South Africa, 12 Sep | [Super Rugby](https://super.rugby/therugbychampionship/news/mounga-to-start-at-10-against-springboks-in-final-rgr-test/) |
| Australia, 10 Oct | [All Blacks](https://www.allblacks.com/news/all-blacks/all-blacks-team-named-for-first-bledisloe-cup-test) |

RNZ's 29 September unavailable line bunches Anton Lienert-Brown, Billy Proctor and Caleb Clarke before the word shoulder. The All Blacks list of 21 September, and ESPN on 29 September, separate them: Lienert-Brown knee, Proctor shoulder, Clarke shoulder, Norris knee. The dossier follows that split.

The meeting notes cite the same public reports as the game-plan section, plus the score sheets. They are not a private All Blacks review.

The earlier player mockup (strengths, development areas, pre-match cues, a six-from-six record, Ellis Park still to come) was a simulation. It is not used.

## Not used as fact

- ESPN's New Zealand team page has a 2026 Top Scorers module labelled The Rugby Championship. Damian McKenzie is listed on 33 points from 6 matches. Will Jordan is not the leading try scorer in that module. It does not match the Test score sheets (Jordan 10 tries, 50 points), so it is not used. The Rugby Championship table on the same page is empty.
- ESPN match attendance stored as 0 is missing data, not a crowd.
- A Dubai Telegraph report called the France Test 32–30. Rugby Database, ESPN, the All Blacks, BBC Sport and the NZ Herald say 34–32.
- ESPN league 242041 is Super Rugby Pacific. It is not the All Blacks Test feed. The page does not use it.
- There is no hand-typed prediction. `data/build_forecast.py` is the only place a win probability can be produced, and it writes one only after a scored Test series clears its gate.

## Forecast model, licences, and what was not used

Checked again on 19 October 2026 (Sydney). The probability reads `data/forecast.json`, which `data/build_forecast.py` writes from `data/rugbydatabase-tests.json`. The page does not type a percentage.

| Source | Used for | Licence / terms |
|---|---|---|
| [Rugby Database, All Test Match Games](https://www.rugbydatabase.com.au/test-rugby/games-list.php) | The scored Test history, with venue and home side. Retrieved 19 October 2026 Sydney time (`retrievedAt` `2026-10-18T21:32:34+00:00`). The file is `data/rugbydatabase-tests.json`. Refresh with `python data/build_forecast.py --fetch-history`. | Rugby Database's published list. Stored with the source URL and the retrieval time. |
| [Rugby Database team games lists](https://www.rugbydatabase.com.au/team/games-list.php?teamId=3) | Coverage cross-check for the Tier 1 unions, including New Zealand (`teamId=3`) and Australia (`teamId=37`). | Same site. The New Zealand list includes tour matches. Those tours are not the model history. |
| [Wikidata Query Service](https://query.wikidata.org/sparql) | Not the series for this probability. The earlier extract is still `data/wikidata-rugby-coverage.json`. It marked a home side on too few scored matches. | CC0 |
| [World Rugby men's rankings](https://www.world.rugby/rankings/mru) | The ranking-gap box only. The snapshot is `data/world-rugby-rankings.json`, effective 12 October 2026. The public feed was read again on 19 October 2026 (Sydney) and the effective date was still 12 October 2026, so the file was not replaced. It is not the pre-match rating for Scotland, because Sydney has been played since that date. | World Rugby's published figures. Not CC0. Stored with attribution. Not a prediction. |
| [World Rugby rankings explanation](https://www.world.rugby/rankings/explanation) | The points exchange, the 15-point margin weighting, and the Wales check (76.92 at home to Scotland 76.36, won 23–10, exchange 0.64). The published three-point home adjustment is that ranking fact and that formula check. | Quoted as the method. |
| [rugbyAPI](https://rugbyapi.com/documentation) | Not this history. A free key covers 11 endpoints and 50 lookups a day, from yesterday forward, without `include`, so it cannot supply the Test series. Current fixtures, results, lineups and timelines still go through `scripts/fetch-rugbyapi.mjs` into `data/rugbyapi-snapshot.json`. | rugbyAPI terms. The key is read from `RUGBYAPI_KEY` and is never committed. If the variable is missing, no request is sent. `GET /v1/matches/{id}?include=lineups,timeline`, `GET /v1/teams/{id}/form` and `GET /v1/players/{id}` need Archive. A `403 plan_required` is stored and nothing is invented. Quality flags decide what is kept: a timeline only when `complete` and the events add up to the score, lineups only when `complete` and no player is on both sides. Scores that disagree with this season file are listed and are not copied onto the season card. |
| [NZ Rugby Stats](https://stats.allblacks.com/all-players) | Official player profile links on the dashboard and the dossier. | Links only. Career figures on those pages are not copied into the JSON. |
| Goalserve | Not used. `src/data/player-provider.js` is the seam a later paid feed would implement. | No Goalserve payload is in the repo. |

The Test list had 5,822 rows on this retrieval. The history file keeps 4,910 scored Tests. It drops 882 women's matches, 15 XV sides, and 15 invitational sides (Barbarians, World XV, British Army, British Empire Services, Queensland, NZEF Kiwis, South America). Duplicate game ids dropped: 0. "All Blacks" is stored as New Zealand. Western Samoa is stored as Samoa. Pacific Islanders, Great Britain, Arabian Gulf, and New Zealand Maori stay as their own sides. Sydney is in the file as Australia 21, New Zealand 43, Accor Stadium, game 30266. No Test-list row is dated after 17 October 2026.

The 2026 tour games 29376, 29377, 29378 and 29380 (Stormers, Sharks, Bulls, Lions) are on the New Zealand team list and are not on the Test list, so they are not in the history. The nine played 2026 Tests in `data/all-blacks-2026.json` match the Test list, read home-first.

The script replays the published points exchange on that file. A venue is a home ground when, before 1 January 2024, it has at least three Tests and one side is home in at least 70 percent of them. Home advantage applies only when that side is the listed home. Other matches stay in the series with advantage 0. The fitted home advantage in this run is 1.2 points (the best training likelihood from 0 to 12, in steps of 0.1). Likelihood at 0 was −2198.9. Likelihood at the published 3 points was −2206.8. Likelihood at 1.2 was −2192.9. It applies on 3,584 matches. Rugby World Cup finals are not marked separately on this list, so the published doubling for a final is not applied. Replay ratings are not the published World Rugby table.

The gate is 200 scored matches with a home side, 80 before 1 January 2024, 30 on or after that date, and 8 each for New Zealand and Australia. This file clears it. The backtest is the 418 matches from 2 February 2024 through 17 October 2026, held out of the fit: 301 winners correct (72.0 percent). Mean absolute margin error 16.3 points. A draw counts as an incorrect winner. The slope of the win line is positive (0.215).

The estimate written on 14 October 2026 for Sydney, before that match was in the history, is kept on the Sydney Test as `modelEstimate`: New Zealand win chance 66.8 percent, expected margin New Zealand by 8.8. The post-match panel compares that stored estimate with the result. It is labelled "Model estimate, not a guarantee". It is not recalculated after the score.

The next Test in the season file is Scotland at Murrayfield on 7 November 2026 local. Scotland are at home because the venue is Murrayfield. `data/forecast.json` stores a New Zealand win chance of 68.9 percent, a Scotland win chance of 27.5 percent, a draw chance of 3.6 percent, and an expected margin of New Zealand by 9.9 points. Those figures are the file, shown to one decimal place. The label is "Model estimate, not a guarantee". The ranking-gap box still uses the published three-point adjustment on the 12 October table and is labelled "Ranking gap, not a prediction". The page also says that table is not the pre-match rating, because Sydney has been played since 12 October. If a later run fails the gate, or a played season score disagrees with the Test list, the script writes no probability and the page shows "Not calculated" with that reason.

Not used, on purpose:

- rugbyAPI, for this history. A free key only covers yesterday onward.
- The Kaggle international Test dataset. Its licence is CC BY-NC-SA.
- ESPN's hidden site API.
- API-Sports API-Rugby.
- Any Opta or Stats Perform feed. The old sample feed name remains in the data file as "Not connected". The page does not show an Opta model.
- Wikidata, for this probability.

## Refresh the rugbyAPI snapshot

The dashboard and the dossier do not call rugbyAPI. They read `data/rugbyapi-snapshot.json`. Until that file has `"connected": true`, the pages keep the season file and say the snapshot is not connected.

From the repo root, with the key only in the environment:

```bash
export RUGBYAPI_KEY='your key'
node scripts/fetch-rugbyapi.mjs
```

Then commit `data/rugbyapi-snapshot.json` and push it. Do not commit `.env` or the key. Running the script without `RUGBYAPI_KEY` sends no request. If a connected snapshot is already in the file, that run leaves it in place.

`node scripts/fetch-rugbyapi.mjs --self-check` checks the quality rules and the cross-check without a key and without writing the snapshot.

What the refresh calls:

- `GET /v1/search?q=New Zealand` and `GET /v1/teams/{id}` to confirm the national side. Both are on the free key.
- `GET /v1/fixtures?days=60` for upcoming Tests.
- `GET /v1/matches?team={id}` for 2026 finished matches. A free key returns `403 plan_required` for dates before yesterday.
- `GET /v1/matches/{id}?include=lineups,timeline`. A free key returns `403 plan_required`. The script then asks for the match without `include`.
- `GET /v1/teams/{id}/form?last=12` and `GET /v1/players/{id}` when a usable lineup has a player id. Both need Archive.

A free key allows 50 lookups a day. The script stops at 24 unless `RUGBYAPI_MAX_REQUESTS` is set lower. Refused calls do not count on rugbyAPI's side, and they are still listed in the snapshot.
