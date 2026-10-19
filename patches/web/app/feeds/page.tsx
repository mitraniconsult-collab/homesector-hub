"use client";

import { useState } from "react";

const markets = ["BG", "RO", "GR", "HU"] as const;
const channels = ["google", "meta", "favi", "biano"] as const;
const feeds = channels.flatMap(channel => markets
  .filter(market => channel !== "biano" || market === "BG")
  .map(market => ({ channel, market })));

export default function FeedsPage() {
  const [filter, setFilter] = useState("all");
  const visible = feeds.filter(feed => filter === "all" || feed.market === filter);
  return (
    <main className="mx-auto max-w-6xl p-6 space-y-6">
      <div>
        <h1 className="text-3xl font-semibold">Feed Manager</h1>
        <p className="mt-2 text-sm text-gray-500">
          Shopify Markets — Google, Meta, FAVI and Biano. Feeds are not published yet.
        </p>
      </div>
      <div className="flex flex-wrap gap-2" aria-label="Filter market">
        {["all", ...markets].map(market => (
          <button key={market} type="button"
            aria-pressed={filter === market}
            className={"rounded border px-3 py-2 " + (filter === market ? "bg-gray-900 text-white" : "")}
            onClick={() => setFilter(market)}>
            {market === "all" ? "All markets" : market}
          </button>
        ))}
      </div>
      <div className="overflow-x-auto rounded border">
        <table className="w-full text-left text-sm">
          <thead className="bg-gray-50"><tr>
            <th className="p-3">Channel</th><th className="p-3">Market</th>
            <th className="p-3">Status</th><th className="p-3">XML URL</th>
          </tr></thead>
          <tbody>
            {visible.map(feed => (
              <tr className="border-t" key={feed.channel + feed.market}>
                <td className="p-3 uppercase">{feed.channel}</td>
                <td className="p-3">{feed.market}</td>
                <td className="p-3">Not published</td>
                <td className="p-3 text-gray-500">Pending validation</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p className="text-sm text-gray-500">
        Feedhub remains active until the new XML endpoints pass validation.
      </p>
    </main>
  );
}
