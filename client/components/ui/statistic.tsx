import React from "react";

export interface StatisticProps {
    value: any;
    label: string;
}

export default function Statistic(props: StatisticProps) {
    return (
        <div className="flex flex-col items-center">
            <span className="text-3xl text-green-200">{props.value}</span>
            <span className="font-semibold">{props.label}</span>
        </div>
    )
}