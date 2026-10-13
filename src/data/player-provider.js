/* Player dossier data layer.
   Pages ask a provider for the dossier and the season file.
   StaticJsonProvider reads the JSON already in this repo.
   GoalserveProvider is the seam for a later paid feed. It does not
   invent players, and it does not run from the browser with a key. */
(function (global) {
  "use strict";

  function ProviderError(code, message) {
    var error = new Error(message);
    error.code = code;
    return error;
  }

  function fetchJson(url) {
    return fetch(url).then(function (response) {
      if (!response.ok) {
        throw ProviderError("HTTP", url + " returned HTTP " + response.status);
      }
      return response.json();
    });
  }

  function StaticJsonProvider(options) {
    this.id = "static-json";
    this.label = "Repo JSON files";
    this.licence = "Transcribed figures. Citations are in data/SOURCES.md.";
    this.base = (options && options.base) || "";
  }

  StaticJsonProvider.prototype.load = function () {
    var base = this.base;
    return Promise.all([
      fetchJson(base + "data/player-dossier-2026.json"),
      fetchJson(base + "data/all-blacks-2026.json")
    ]).then(function (pair) {
      return {
        provider: "static-json",
        dossier: pair[0],
        season: pair[1]
      };
    });
  };

  function GoalserveProvider(options) {
    this.id = "goalserve";
    this.label = "Goalserve";
    this.configured = Boolean(options && options.apiKey);
    /* A browser page must not hold this key. A future build step would
       pass it from the environment and write JSON for StaticJsonProvider. */
  }

  GoalserveProvider.prototype.load = function () {
    if (!this.configured) {
      return Promise.reject(ProviderError(
        "NOT_CONFIGURED",
        "Goalserve is not configured. No player feed was requested, and no sample squad is shown."
      ));
    }
    return Promise.reject(ProviderError(
      "NOT_IMPLEMENTED",
      "The Goalserve adapter is not switched on. It will not invent player data."
    ));
  };

  function createPlayerProvider(options) {
    var settings = options || {};
    if (settings.provider === "goalserve") {
      return new GoalserveProvider(settings);
    }
    return new StaticJsonProvider(settings);
  }

  global.MatakiteData = {
    createPlayerProvider: createPlayerProvider,
    StaticJsonProvider: StaticJsonProvider,
    GoalserveProvider: GoalserveProvider
  };
})(window);
