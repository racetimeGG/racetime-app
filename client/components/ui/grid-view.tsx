import React from "react";

export interface GridViewProps<T> {
    /**
     * The initial data to show.
     */
    initialData: T[];

    /**
     * The initial page number of the shown data.
     */
    initialPage: number;

    /**
     * loadPage is a callback that loads the data on a given page number. This function must return either an array of
     * T representing the new data, or null to signify there is no further data.
     * @param page The page number
     * @return An array of T or null
     */
    loadPage: (page: number) => T[] | null;
}

export default function GridView<T>(props: GridViewProps<T>) {
    const [columns, setColumns] = React.useState<number>(0);

    return (
        <div className="grid-view">
            <div>1</div>
            <div>2</div>
            <div>3</div>
            <div>4</div>
            <div>5</div>
            <div>6</div>
            <div>7</div>
            <div>8</div>
        </div>
    );
}