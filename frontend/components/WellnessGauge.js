"use client";

import { RadialBarChart, RadialBar, PolarAngleAxis } from "recharts";

const BAND_COLORS = {
  Good: "#00C49A",
  Fair: "#00808A",
  "Needs attention": "#D98E04",
  Poor: "#B83A3A",
};

export default function WellnessGauge({ total, band }) {
  const color = BAND_COLORS[band] || "#00808A";
  const data = [{ value: total, fill: color }];

  return (
    <div className="relative flex flex-col items-center" style={{ width: 220, height: 140 }}>
      <RadialBarChart
        width={220}
        height={140}
        cx="50%"
        cy="100%"
        innerRadius="70%"
        outerRadius="100%"
        barSize={18}
        data={data}
        startAngle={180}
        endAngle={0}
      >
        <PolarAngleAxis type="number" domain={[0, 100]} angleAxisId={0} tick={false} />
        <RadialBar background={{ fill: "#E7EFEE" }} dataKey="value" cornerRadius={9} />
      </RadialBarChart>
      <div className="absolute inset-x-0 bottom-2 flex flex-col items-center">
        <span className="font-heading text-4xl font-bold text-ink">{total}</span>
        <span className="text-sm font-medium" style={{ color }}>
          {band}
        </span>
      </div>
    </div>
  );
}
