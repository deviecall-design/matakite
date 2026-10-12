# Sources for the 2026 All Blacks record

Checked on 28 September 2026, again on 7 October 2026 for the player dossier, and again on 12 October 2026 after Eden Park. The Rugby Database games list now has one game after Baltimore: 10 October, All Blacks 50–19 Australia at Eden Park, crowd 46,352, game 30265. The ESPN match page shows the same score. Sydney on 17 October is not on the Rugby Database list and had not been played. No other All Blacks game since 12 September is on that list.

The player dossier is `player-dossier.html`. It reads `data/player-dossier-2026.json` and this season file. Every score on the page is New Zealand first, then the opponent. Rugby Database lists the home side first, so away results are flipped to keep New Zealand first.

The page reads `data/all-blacks-2026.json`. `data/compute_season_stats.py` adds the season totals and stops if a Test score sheet does not add up to the final score. The page does the same sum again when it loads.

## How the two main sources were used

Primary source for played results, venues and crowds: [Rugby Database, New Zealand games list](https://www.rugbydatabase.com.au/team/games-list.php?teamId=3). The list is embedded in the page. A plain fetch without a browser Accept header was refused (HTTP 406). With a normal browser header the list loaded. Each played game below links to its Rugby Database game page.

Cross-check for Tests: [ESPN New Zealand team page](https://www.espn.com.au/rugby/team/_/id/8/new-zealand) and its [2026 results list](https://www.espn.com.au/rugby/results/_/team/8/). The ESPN website returned the pages (HTTP 200) with a normal browser user agent. An earlier audit found the ESPN site API returned HTTP 403 from this machine. That API was not used. The HTML pages were not blocked.

ESPN's results list, when it was read in September, had the seven Tests through Baltimore. Scores agreed with Rugby Database on all seven. On 12 October a direct fetch of that results page was blocked by a bot check. The Eden Park match page was read from an index and agrees at 50–19. The four tour matches were checked against the [Wikipedia tour page](https://en.wikipedia.org/wiki/2026_New_Zealand_rugby_union_tour_of_South_Africa).

These ESPN paths did not give the New Zealand upcoming list, so they were not used as a fixture source:

- `https://www.espn.com.au/rugby/fixtures/_/team/8/` returned a generic rugby fixtures page, not the All Blacks list.
- `https://www.espn.com.au/rugby/team/fixtures/_/id/8/` and `https://www.espn.com.au/rugby/team/squad/_/id/8/nzl` returned HTTP 404.

Upcoming fixtures stay on allblacks.com. On 12 Oct 2026 the Rugby Database list's newest game was Eden Park. Sydney and the November Tests were not on it.

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

Try scorers for those Tests come from match reports, not from Rugby Database (its game pages do not list a full try sequence):

- France: [All Blacks](https://www.allblacks.com/news/all-blacks/all-blacks-edge-france-in-christchurch-thriller-to-open-2026), [BBC Sport](https://www.bbc.com/sport/rugby-union/articles/c5yze25d46do), [NZ Herald](https://www.nzherald.co.nz/sport/rugby/all-blacks/all-blacks-v-france-result-dave-rennie-era-begins-with-nail-biting-win-in-christchurch/XMVJFMPVYVAONARUXCGHTFY6NY/).
- Italy: [All Blacks](https://www.allblacks.com/news/all-blacks/will-jordan-breaks-all-blacks-try-scoring-record-in-47-17-win-over-italy), [Sky Sports](https://www.skysports.com/rugby-union/new-zealand-vs-italy/111670), [BBC Sport](https://www.bbc.com/sport/rugby-union/articles/c24y0lpj227o).
- Ireland: [All Blacks](https://www.allblacks.com/news/all-blacks/match-report-all-blacks-vs-ireland-nations-championship), [BBC Sport](https://www.bbc.com/sport/rugby-union/articles/c4gk5exp8eko).
- Emirates Airline Park: [All Blacks](https://www.allblacks.com/news/all-blacks/match-report-all-blacks-v-springboks-first-test-rugby-s-greatest-rivalry), [Sky Sports](https://www.skysports.com/rugby-union/news/12321/13575921/south-africa-vs-new-zealand-all-blacks-emerge-worthy-winners-as-they-outscore-springboks-in-first-test-upset).
- Cape Town Stadium: [Sky Sports](https://www.skysports.com/rugby-union/south-africa-vs-new-zealand/111659), [BBC Sport](https://www.bbc.co.uk/sport/rugby-union/match/EVP5649499), [AP](https://apnews.com/article/south-africa-springboks-all-blacks-2nd-test-b996752150947b828d8c0aff1adda7f0).
- First National Bank Stadium: [BBC Sport](https://www.bbc.com/sport/rugby-union/articles/c7830m55lklo), [Sky Sports](https://www.skysports.com/rugby-union/news/13582037/south-africa-29-24-new-zealand-springboks-edge-thriller-to-take-2-1-series-lead-in-soweto).
- Baltimore: [BBC Sport](https://www.bbc.com/sport/rugby-union/articles/c07lmxpmvr9o), [Sky Sports](https://www.skysports.com/rugby-union/news/12321/13584821/south-africa-vs-new-zealand-springboks-show-steel-to-secure-43-28-victory-and-3-1-series-win-against-all-blacks), [All Blacks](https://www.allblacks.com/news/all-blacks/all-blacks-return-to-hilux-npc-as-focus-shifts-to-bledisloe).
- Eden Park: [BBC Sport](https://www.bbc.co.uk/sport/rugby-union/articles/c9zrdl4028mko), [Sky Sports](https://www.skysports.com/rugby-union/news/13596830/new-zealand-50-19-australia-all-blacks-power-to-eden-park-victory-to-retain-bledisloe-cup-for-24th-year), [ESPN](https://www.espn.com/rugby/story/_/id/50145167/bledisloe-cup-australia-new-zealand-all-blacks-punish-wayward-wallabies-second-half-blowout-eden-park), [1News](https://www.1news.co.nz/2026/10/10/all-blacks-regain-confidence-in-bledisloe-cup-rout/). Rugby Database's own game page also lists the try scorers and the kickers, and they match those reports.

Series result against South Africa: South Africa won 3–1. The Bledisloe Cup was retained at Eden Park. Australia can still win the Sydney Test. They cannot take the cup from this result.

Test record from the score sheets: played 8, won 5, lost 3, drawn 0, points for 282, points against 210, tries for 42, tries against 26. Will Jordan has 11 tries and 55 points, the most of both on those sheets.

## Tour matches (not Tests)

These four are on the Rugby Database list under "All Blacks in South Africa & United States - 2026". They are not on the ESPN New Zealand results list. Scores match Wikipedia. No try scorers are shown.

| Date | Opponent | Venue | Crowd | Result | Rugby Database |
|---|---|---|---|---|---|
| 7 Aug 2026 | Stormers | Cape Town Stadium | 47,130 | Won 38–21 | [game 29376](https://www.rugbydatabase.com.au/game.php?gameId=29376) |
| 11 Aug 2026 | Sharks | Kings Park Stadium | 14,759 | Won 54–0 | [game 29377](https://www.rugbydatabase.com.au/game.php?gameId=29377) |
| 15 Aug 2026 | Bulls | Loftus Versfeld Stadium | 30,930 | Won 50–19 | [game 29378](https://www.rugbydatabase.com.au/game.php?gameId=29378) |
| 25 Aug 2026 | Lions | Emirates Airline Park | 15,956 | Won 41–35 | [game 29380](https://www.rugbydatabase.com.au/game.php?gameId=29380) |

All games on that list: played 12, won 9, lost 3, drawn 0, points for 465, points against 285. Try totals stay on the eight Tests. Eden Park is the twelfth game.

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

Eden Park has been played. These were not on the Rugby Database games list on 12 Oct 2026.

| Date on the page | Opponent | Venue | Note | Source |
|---|---|---|---|---|
| 17 Oct 2026 | Australia | Accor Stadium, Sydney | Not played. Kick-off not verified. allblacks.com says 6.00pm New Zealand time. Accor Stadium says 3.45pm local. Sky Sports says 6am BST. | [All Blacks](https://www.allblacks.com/news/all-blacks/all-blacks-return-to-hilux-npc-as-focus-shifts-to-bledisloe), [Accor Stadium](https://www.accorstadium.com.au/events/n2026_bledisloe_cup_wallabies_v_all_blacks), [Sky Sports](https://www.skysports.com/rugby-union/news/13596830/new-zealand-50-19-australia-all-blacks-power-to-eden-park-victory-to-retain-bledisloe-cup-for-24th-year) |
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
- There is no prediction model, so there are no win percentages, Brier scores, or hit rates.
