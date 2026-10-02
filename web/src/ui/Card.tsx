import { useRef } from "react";
import type { HTMLAttributes, MouseEvent, ReactElement, ReactNode } from "react";

interface CardProps extends HTMLAttributes<HTMLElement> {
  children: ReactNode;
  spotlight?: boolean;
}

interface SectionProps {
  children: ReactNode;
  className?: string;
}

/* Compound Card in the PanelUI idiom: Card.Header / Title / Description /
   Content / Footer compose the way the markup reads. Spotlight hover
   follows the cursor (React Bits "Spotlight Card"). */
function CardBase({ children, spotlight = true, className = "", ...rest }: CardProps): ReactElement {
  const ref = useRef<HTMLElement>(null);

  function onMove(e: MouseEvent<HTMLElement>) {
    const el = ref.current;
    if (!el) return;
    const r = el.getBoundingClientRect();
    el.style.setProperty("--mx", `${e.clientX - r.left}px`);
    el.style.setProperty("--my", `${e.clientY - r.top}px`);
  }

  return (
    <section
      ref={ref}
      onMouseMove={spotlight ? onMove : undefined}
      className={`rcard${spotlight ? " rcard-spot" : ""} ${className}`}
      {...rest}
    >
      {children}
    </section>
  );
}

function Header({ children, className = "" }: SectionProps): ReactElement {
  return <div className={`rcard-header ${className}`}>{children}</div>;
}

function Title({ children, className = "" }: SectionProps): ReactElement {
  return <h2 className={`rcard-title ${className}`}>{children}</h2>;
}

function Description({ children, className = "" }: SectionProps): ReactElement {
  return <p className={`rcard-desc ${className}`}>{children}</p>;
}

function Content({ children, className = "" }: SectionProps): ReactElement {
  return <div className={`rcard-content ${className}`}>{children}</div>;
}

function Footer({ children, className = "" }: SectionProps): ReactElement {
  return <div className={`rcard-footer ${className}`}>{children}</div>;
}

type CardStatics = {
  Header: typeof Header;
  Title: typeof Title;
  Description: typeof Description;
  Content: typeof Content;
  Footer: typeof Footer;
};

const Card = CardBase as typeof CardBase & CardStatics;
Card.Header = Header;
Card.Title = Title;
Card.Description = Description;
Card.Content = Content;
Card.Footer = Footer;

export default Card;
