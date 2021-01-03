import React from "react";

interface ButtonProps {

}

export default function Button(props: React.PropsWithChildren<ButtonProps>) {
    return (
        <button>{props.children}</button>
    )
}