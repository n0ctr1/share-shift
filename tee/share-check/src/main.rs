//! Recomputes the headline NEAR Intents market share inside an OutLayer TEE.
//!
//! Input (stdin, JSON):  {"from_ts": 1786579200, "to_ts": 1794268800}
//!   both inclusive, UTC day starts, as unix seconds.
//!
//! The program fetches, by itself, the same public sources the Python build
//! uses: DefiLlama daily volume for the four swap venues, and THORChain's and
//! Maya's Midgard daily leg breakdown. It returns (stdout, JSON, under 900
//! bytes so it fits a NEAR transaction):
//!   - each venue's volume over the window (USD, millions),
//!   - the Intents share as reported,
//!   - THORChain's and Maya's fraction left when each routed swap is counted
//!     once,
//!   - the Intents share with Intents and those two rivals halved accordingly
//!     (Chainflip is left as reported here; its leg data needs ~200 indexer
//!     pages, too many for one run),
//!   - the SHA-256 of every response body it read.

use serde_json::{json, Value};
use sha2::{Digest, Sha256};
use std::io::{self, Read, Write};
use std::time::Duration;
use wasi_http_client::Client;

const VENUES: [&str; 4] = ["near-intents", "thorchain-dex", "chainflip-amm", "maya-protocol"];
const MIDGARD: [(&str, &str); 2] = [
    ("thorchain-dex", "https://gateway.liquify.com/chain/thorchain_midgard/v2/history/swaps?interval=day&count=400"),
    ("maya-protocol", "https://midgard.mayachain.info/v2/history/swaps?interval=day&count=400"),
];
const PAIRS: [(&str, &str); 3] = [
    ("toRuneVolume", "toAssetVolume"),
    ("fromTradeVolume", "toTradeVolume"),
    ("fromSecuredVolume", "toSecuredVolume"),
];

fn fetch(url: &str) -> Result<(Value, String), Box<dyn std::error::Error>> {
    let mut last = String::new();
    for _ in 0..4 {
        match fetch_once(url) {
            Ok(v) => return Ok(v),
            Err(e) => last = e.to_string(),
        }
    }
    Err(last.into())
}

fn fetch_once(url: &str) -> Result<(Value, String), Box<dyn std::error::Error>> {
    let response = Client::new()
        .get(url)
        .header("User-Agent", "share-shift/1.0")
        .connect_timeout(Duration::from_secs(20))
        .send()?;
    let status = response.status();
    if status != 200 {
        return Err(format!("{} answered {}", url, status).into());
    }
    let body = response.body()?;
    let body = body.as_slice();
    let digest = Sha256::digest(body);
    let hex: String = digest.iter().map(|b| format!("{:02x}", b)).collect();
    Ok((serde_json::from_slice(body)?, hex[..16].to_string()))
}

fn num(v: &Value) -> f64 {
    match v {
        Value::Number(n) => n.as_f64().unwrap_or(0.0),
        Value::String(s) => s.parse().unwrap_or(0.0),
        _ => 0.0,
    }
}

fn round(x: f64, digits: i32) -> f64 {
    let p = 10f64.powi(digits);
    (x * p).round() / p
}

fn main() -> Result<(), Box<dyn std::error::Error>> {
    let mut raw = String::new();
    io::stdin().read_to_string(&mut raw)?;
    let input: Value = serde_json::from_str(&raw)?;
    let from = num(&input["from_ts"]) as i64;
    let to = num(&input["to_ts"]) as i64;

    let mut volume = [0.0f64; 4];
    let mut hashes = serde_json::Map::new();
    for (i, slug) in VENUES.iter().enumerate() {
        let (body, hash) = fetch(&format!("https://api.llama.fi/summary/dexs/{}", slug))?;
        for point in body["totalDataChart"].as_array().ok_or("no totalDataChart")? {
            let ts = num(&point[0]) as i64;
            if ts >= from && ts <= to {
                volume[i] += num(&point[1]);
            }
        }
        hashes.insert(slug.to_string(), json!(hash));
    }

    let mut once = [1.0f64; 4];
    for (slug, url) in MIDGARD.iter() {
        let (body, hash) = match fetch(url) {
            Ok(v) => v,
            Err(_) => {
                hashes.insert(format!("midgard-{}", slug), json!("unavailable"));
                continue;
            }
        };
        let (mut total, mut paired) = (0.0f64, 0.0f64);
        let mut legs = [(0.0f64, 0.0f64); 3];
        for interval in body["intervals"].as_array().ok_or("no intervals")? {
            let ts = num(&interval["startTime"]) as i64;
            if ts < from || ts > to {
                continue;
            }
            total += num(&interval["totalVolume"]);
            for (k, (a, b)) in PAIRS.iter().enumerate() {
                legs[k].0 += num(&interval[*a]);
                legs[k].1 += num(&interval[*b]);
            }
        }
        for (a, b) in legs.iter() {
            paired += 2.0 * a.min(*b);
        }
        let idx = VENUES.iter().position(|v| v == slug).unwrap();
        if total > 0.0 {
            once[idx] = 1.0 - paired / total / 2.0;
        }
        hashes.insert(format!("midgard-{}", slug), json!(hash));
    }

    let total: f64 = volume.iter().sum();
    let reported = volume[0] / total;
    let adjusted: Vec<f64> = (0..4)
        .map(|i| volume[i] * if i == 0 { 0.5 } else { once[i] })
        .collect();
    let one_side = adjusted[0] / adjusted.iter().sum::<f64>();

    let out = json!({
        "v": 1,
        "from_ts": from,
        "to_ts": to,
        "volume_musd": {
            "near-intents": round(volume[0] / 1e6, 1),
            "thorchain-dex": round(volume[1] / 1e6, 1),
            "chainflip-amm": round(volume[2] / 1e6, 1),
            "maya-protocol": round(volume[3] / 1e6, 1),
        },
        "share_reported": round(reported, 4),
        "once_thorchain": round(once[1], 4),
        "once_maya": round(once[3], 4),
        "share_one_side_cf_as_reported": round(one_side, 4),
        "sha256_16": hashes,
    });
    print!("{}", serde_json::to_string(&out)?);
    io::stdout().flush()?;
    Ok(())
}
