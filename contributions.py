# To add a new cell, type '# %%'
# To add a new markdown cell, type '# %% [markdown]'
# %%
import os
from datetime import datetime
from IPython.core.display import ProgressBar

import numpy as np
import pandas as pd
from gql import gql, Client, AIOHTTPTransport
import asyncio


TOP = 100

TOKEN = "bearer " + os.getenv("GH_GQL_API_TOKEN")

# Select your transport with a GitHub url endpoint
transport = AIOHTTPTransport(
    url="https://api.github.com/graphql", headers={"Authorization": TOKEN}
)

client = Client(transport=transport, fetch_schema_from_transport=True,)


def progress(percent=0, width=30):
    "Print simple progress bar"
    left = int(width * percent // 100)
    right = width - left
    print(
        "\r[",
        "=" * left,
        " " * right,
        "]",
        f" {percent:.0f}%",
        sep="",
        end="",
        flush=True,
    )


async def main():

    # Using `async with` on the client will start a connection on the transport
    # and provide a `session` variable to execute queries on this connection
    async with client as session:
        # Provide a GraphQL query
        query = gql(
            """
            query search($query: String!, $type: SearchType!, $numOfResults: Int!, $nextPageCursor: String) {
              search(type: $type, query: $query, first: $numOfResults, after: $nextPageCursor) {
                pageInfo {
                  hasNextPage
                  endCursor
                }
                userCount
                nodes {
                  ... on User {
                    name
                    login
                    location
                    bio
                    avatarUrl
                    followers {
                      totalCount
                    }
                    contributionsCollection {
                      contributionCalendar{
                        totalContributions
                      }
                      totalCommitContributions
                      totalPullRequestContributions
                      restrictedContributionsCount
                    }
                  }
                }
              }
            }
        """
        )

        params = {"query": "location:Cuba", "type": "USER", "numOfResults": 20}

        print("Getting users...")

        result_users = []
        result_count = 0
        result_next = True
        first = True
        pb = ProgressBar(result_count)

        while result_next:
            try:
                result = await session.execute(query, variable_values=params)
            except asyncio.exceptions.TimeoutError:
                continue

            result_users += result.get("search").get("nodes", [])
            result_count = result.get("search").get("userCount", 0)

            if first:
                pb.total = result_count
                first = False

            pb._progress = len(result_users)
            result_next = result.get("search").get("pageInfo").get("hasNextPage", False)
            params["nextPageCursor"] = (
                result.get("search").get("pageInfo").get("endCursor")
            )
            progress(len(result_users) * 100 / result_count)
            await asyncio.sleep(1)

        users = result_users
        print("\nTotal GitHub Users from Cuba: %s" % len(users))

        try:
            assert len(users) > 0
        except AssertionError:
            raise Exception("ERROR: Unavailable users!")

        for user in users:
            if user:
                user["followers"] = user.get("followers").get("totalCount", 0)
                user["contributions"] = user.get("contributionsCollection").get(
                    "contributionCalendar"
                ).get("totalContributions", 0) - user.get(
                    "contributionsCollection"
                ).get(
                    "restrictedContributionsCount", 0
                )
                user["commits"] = user.get("contributionsCollection").get(
                    "totalCommitContributions", 0
                ) + user.get("contributionsCollection").get(
                    "totalPullRequestContributions", 0
                )
                del user["contributionsCollection"]

        df = pd.DataFrame(users)
        df.dropna(how="all", inplace=True)
        # df = df.reset_index(drop=True)
        df = df.sort_values(by="commits", ascending=False)

        # Top Ten Cuba
        new_dtypes = {
            "followers": np.int64,
            "contributions": np.int64,
            "commits": np.int64,
        }
        position = ["\U0001F947", "\U0001F948", "\U0001F949"] + list(range(4, TOP + 1))

        df_top_ten = df[:TOP]
        df_top_ten = df_top_ten.astype(new_dtypes)
        # Clean
        df_top_ten.fillna("", inplace=True)
        # Re-Order Columns
        df_top_ten = df_top_ten[
            [
                "name",
                "login",
                "location",
                "commits",
                "contributions",
                "followers",
                "bio",
                "avatarUrl",
            ]
        ]
        df_top_ten.insert(0, "#", position)
        print("Top %s of %s GitHub Users from Cuba" % (TOP, len(users)))
        print("Generated at: %s UTC" % datetime.utcnow())
        table_name = "table_cuba_contributions.html"
        df_top_ten.to_html(buf=table_name, index=False)
        print("Saved table: %s" % table_name)


loop = asyncio.get_event_loop()
loop.run_until_complete(main())
