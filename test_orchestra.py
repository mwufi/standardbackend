# from mainframe_orchestra import Agent, Task, OpenaiModels, WebTools, set_verbosity

# set_verbosity(1)

# research_agent = Agent(
#     agent_id="research_assistant_1",
#     role="research assistant",
#     goal="answer user queries",
#     llm=OpenaiModels.gpt_4o,
#     tools={WebTools.exa_search}
# )

# def research_task(topic):
#     return Task.create(
#         agent=research_agent,
#         instruction="Find me 100 VC firms in NYC",
#     )

# result = research_task("quantum computing")
# print(result)

from mainframe_orchestra import Agent, Task, WebTools, WikipediaTools, AmadeusTools, OpenrouterModels, set_verbosity
from datetime import datetime

set_verbosity(1)

web_research_agent = Agent(
    agent_id="web_research_agent",
    role="web research agent",
    goal="search the web thoroughly for travel information",
    attributes="hardworking, diligent, thorough, comphrehensive.",
    llm=OpenrouterModels.gpt_4o,
    tools=[WebTools.serper_search, WikipediaTools.search_articles, WikipediaTools.search_images]
)

travel_agent = Agent(
    agent_id="travel_agent",
    role="travel agent",
    goal="assist the traveller with their request",
    attributes="frindly, hardworking, and comprehensive and extensive in reporting back to users",
    llm=OpenrouterModels.gpt_4o,
    tools=[AmadeusTools.search_flights, WebTools.serper_search, WebTools.get_weather_data]
)

# Define the taskflow

def research_destination(destination, interests):
    destination_report = Task.create(
        agent=web_research_agent,
        context=f"User Destination: {destination}\nUser Interests: {interests}",
        instruction=f"Use your tools to search relevant information about the given destination: {destination}. Use wikipedia tools to search the destination's wikipedia page, as well as images of the destination. In your final answer you should write a comprehensive report about the destination with images embedded in markdown."
    )
    return destination_report

def research_events(destination, dates, interests):
    events_report = Task.create(
        agent=web_research_agent,
        context=f"User's intended destination: {destination}\n\nUser's intended dates of travel: {dates}\nUser Interests: {interests}",
        instruction="Use your tools to research events in the given location for the given date span. Ensure your report is a comprehensive report on events in the area for that time period."
    )
    return events_report

def research_weather(destination, dates):
    current_date = datetime.now().strftime("%Y-%m-%d")
    weather_report = Task.create(
        agent=travel_agent,
        context=f"Location: {destination}\nDates: {dates}\n(Current Date: {current_date})",
        instruction="Use your weather tool to search for weather information in the given dates and write a report on the weather for those dates. Do not be concerned about dates in the future; ** IF dates are more than 10 days away, user web search instead of weather tool. If the dates are within 10 days, use the weather tool. ** Always search for weather information regardless of the date you think it is."
    )
    return weather_report

def search_flights(current_location, destination, dates):
    flight_report = Task.create(
        agent=travel_agent,
        context=f"Current Location: {current_location}\n\nDestination: {destination}\nDate Range: {dates}",
        instruction=f"Search for a lot of flights in the given date range to collect a bunch of options and return a report on the best options in your opinion, based on convenience and lowest price."
    )
    return flight_report

def write_travel_report(destination_report, events_report, weather_report, flight_report):
    travel_report = Task.create(
        agent=travel_agent,
        context=f"Destination Report: {destination_report}\n--------\n\nEvents Report: {events_report}\n--------\n\nWeather Report: {weather_report}\n--------\n\nFlight Report: {flight_report}",
        instruction=f"Write a comprehensive travel plan and report given the information above. Ensure your report conveys all the detail in the given information, from flight options, to weather, to events, and image urls, etc. Preserve detail and write your report in extensive length."
    )
    return travel_report

def main():
    current_location = input("Enter current location: ")
    destination = input("Enter destination: ")
    dates = input("Enter dates: ")
    interests = input("Enter interests: ")

    destination_report = research_destination(destination, interests)
    print(destination_report)
    events_report = research_events(destination, dates, interests)
    print(events_report)
    weather_report = research_weather(destination, dates)
    print(weather_report)
    flight_report = search_flights(current_location, destination, dates)
    print(flight_report)
    travel_report = write_travel_report(destination_report, events_report, weather_report, flight_report)
    print(travel_report)

if __name__ == "__main__":
    main()