import { Pushback } from "@/components/Pushback";
import { Desk } from "@/components/desk/Desk";

export default function Page() {
  return (
    <>
      <Desk />
      <Pushback>
        The desk shows that a number agrees with the query it cites, not that the query was the right one; the graders on the scorecard check that separately. On a free tier the live answer may come from the floor, and the badge says so.
      </Pushback>
    </>
  );
}
