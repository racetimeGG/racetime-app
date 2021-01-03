import React from "react";
import GridView from "../../components/ui/grid-view";

export default function() {
    return (
        <React.Fragment>
            <GridView initialData={[]} initialPage={1} loadPage={() => []} />
        </React.Fragment>
    )
}
