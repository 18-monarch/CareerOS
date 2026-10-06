FUNNEL = ["APPLIED", "OA_RECEIVED", "OA_COMPLETED", "INTERVIEW", "OFFER"]


def funnel(applications):
    # Count historical milestones, never just current statuses (rejections preserve conversion).
    counts = dict.fromkeys(FUNNEL, 0)
    counts["FINAL_ROUND"] = 0
    for app in applications:
        reached = {e.status for e in app.events}
        if app.applied_at:
            reached.add("APPLIED")
        if "FINAL_ROUND" in reached or "OFFER" in reached:
            reached.add("INTERVIEW")
        for stage in counts:
            counts[stage] += int(stage in reached)

    def rate(n, d):
        return round(100 * n / d, 1) if d else None

    rates = {
        "oa_rate": rate(counts["OA_RECEIVED"], counts["APPLIED"]),
        "oa_completion_rate": rate(counts["OA_COMPLETED"], counts["OA_RECEIVED"]),
        "interview_rate": rate(counts["INTERVIEW"], counts["APPLIED"]),
        "offer_rate": rate(counts["OFFER"], counts["APPLIED"]),
    }
    oa_done = [a for a in applications if any(e.status == "OA_COMPLETED" for e in a.events)]
    oa_pass = sum(
        any(e.status in ("INTERVIEW", "FINAL_ROUND", "OFFER") for e in a.events) for a in oa_done
    )
    rates["oa_pass_rate"] = rate(oa_pass, len(oa_done))
    if counts["APPLIED"] < 10:
        recommendation = "Too little data for a reliable bottleneck diagnosis. Track at least 10 applications and their outcomes."
    elif len(oa_done) >= 5 and rates["oa_pass_rate"] is not None and rates["oa_pass_rate"] < 30:
        recommendation = "Recorded OA-to-interview conversion is low. Review OA/DSA preparation; pending results may still change this signal."
    elif (rates["oa_rate"] or 0) < 20 and (rates["interview_rate"] or 0) < 20:
        recommendation = "Early-stage responses are low. Review targeting, resume evidence and referrals; response delays may affect this signal."
    else:
        recommendation = "No clear bottleneck in the recorded sample. Keep preparing for the next scheduled stage."
    return {
        "counts": counts,
        "rates": rates,
        "sample_size": counts["APPLIED"],
        "recommendation": recommendation,
        "note": "Milestone rates use recorded history; companies may skip OAs and pending outcomes remain unresolved.",
    }
