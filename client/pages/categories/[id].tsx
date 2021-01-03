import React from "react";
import {GetServerSideProps} from "next";
import Link from "next/link";
import Axios from "axios";

import CategoryHeader from "../../components/category/category-header";
import {CategoryDetail} from "../../lib/category";
import {RacesData} from "../../lib/race";
import RaceCard from "../../components/race/race-card";

interface CategoryProps {
    category: CategoryDetail;
    raceData: RacesData;
}

export default function CategoryPage(props: CategoryProps) {
    return (
        <div>
            <CategoryHeader category={props.category}/>
            <div>
                {props.raceData.races.map(race => (
                    <RaceCard key={race.name} race={race}/>
                ))}
            </div>
        </div>
    )
}

export const getServerSideProps: GetServerSideProps<CategoryProps> = async (context) => {
    const page = context.query.page ? context.query.page as string : '1';
    const category = await Axios.get<CategoryDetail>(`https://racetime.gg/${context.params.id}/data`);
    const races = await Axios.get<RacesData>(`https://racetime.gg/${context.params.id}/races/data?page=${page}`);

    return {
        props: {
            category: category.data,
            raceData: races.data,
        }
    };
}
