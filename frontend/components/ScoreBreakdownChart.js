"use client";

import { Bar, BarChart, CartesianGrid, Legend, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

export default function ScoreBreakdownChart({ breakdown }) {
  if (!breakdown || breakdown.length === 0) {
    return <p className="text-sm text-muted">No score breakdown available.</p>;
  }

  const data = breakdown.map((item) => ({
    factor: item.factor ? item.factor.charAt(0).toUpperCase() + item.factor.slice(1) : "-",
    points: item.points ?? 0,
    weight: item.weight ?? 0,
  }));

  return (
    <ResponsiveContainer width="100%" height={260}>
      <BarChart data={data} layout="vertical" margin={{ left: 8, right: 16, top: 4, bottom: 4 }}>
        <CartesianGrid strokeDasharray="3 3" horizontal={false} stroke="#D8E3E1" />
        <XAxis type="number" tick={{ fontSize: 11, fill: "#5B7478" }} />
        <YAxis type="category" dataKey="factor" width={64} tick={{ fontSize: 11, fill: "#5B7478" }} />
        <Tooltip />
        <Legend wrapperStyle={{ fontSize: 11 }} />
        <Bar dataKey="weight" fill="#D8E3E1" name="Weight available" radius={[0, 4, 4, 0]} />
        <Bar dataKey="points" fill="#00808A" name="Points earned" radius={[0, 4, 4, 0]} />
      </BarChart>
    </ResponsiveContainer>
  );
}
