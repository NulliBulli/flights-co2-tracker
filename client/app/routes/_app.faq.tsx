import type { AccordionItem } from "~/components/Accordion";
import Accordion from "~/components/Accordion";

function Faq() {
  const questions: AccordionItem[] = [
    {
      title: "What is the goal of this page?",
      content:
        "This page allows users to visualize and explore carbon emissions generated by flights in specific airspaces and by specific aircrafts. With this dashboard, you can gain insights into the environmental impact of air traffic and monitor carbon emissions over time.",
    },
    {
      title: "Where does the data come from?",
      content:
        "The data is sourced from the OpenSky API, which provides access to state vectors in airspaces and flight data. It offers a comprehensive set of information related to aircraft positions, velocities, and other relevant data points.",
    },
    {
      title: "How accurate is the data?",
      content:
        "Many estimations and assumptions are made (airplanes leave the airspace in a straight path, a constant speed of 700 km/h is assumed for distance calculations with Celebs, fuel consumption is estimated based on the aircraft type, etc.). Therefore, there is no guarantee of the correctness and accuracy of the data.\nThe calculation process involves obtaining state vectors, which are then used to calculate aircraft flight paths. Subsequently, the CO2 emissions are estimated based on the aircraft type, utilizing the Flight Fuel Consumption API.",
    },
    {
      title: "How often does the data update?",
      content:
        "The data updates at specific intervals as follows:\n- Airspace statistics are refreshed every minute.\n- The airspace chart is updated on an hourly basis.\n- The celebrity leaderboard is updated daily.",
    },
    {
      title: "How does the data compare?",
      content:
        'This can be answered with the following citation:\n"According to figures from German nonprofit Atmosfair, flying from London to New York and back generates about 986kg of CO2 per passenger. There are 56 countries where the average person emits less carbon dioxide in a whole year – from Burundi in Africa to Paraguay in South America.\nBut even a relatively short return trip from London to Rome carries a carbon footprint of 234kg of CO2 per passenger – more than the average produced by citizens of 17 countries annually."',
      links: [
        {
          title: "Source",
          link: "https://www.theguardian.com/environment/ng-interactive/2019/jul/19/carbon-calculator-how-taking-one-flight-emits-as-much-as-many-people-do-in-a-year",
        },
      ],
    },
  ];

  return (
    <div className="w-full lg:w-2/3">
      <Accordion items={questions} />
    </div>
  );
}
export default Faq;
