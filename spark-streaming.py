import pyspark
from pyspark.sql import SparkSession
from pyspark.sql.types import StructType, StructField, StringType, IntegerType, TimestampType
from pyspark.sql.functions import from_json, col
from pyspark.sql.functions import sum as _sum

if __name__ == "__main__":
    spark = (SparkSession.builder
             .appName("RealtimeVoting")
             .master('local[*]')
             .config('spark.jars.packages',
                     'org.apache.spark:spark-sql-kafka-0-10_2.12:3.5.0')
             .config('spark.jars', 'D:\Workspace\pyWorkspace\pythonProject\RealtimeVoting\postgresql-42.7.1.jar')
             .config('spark.sql.adaptive.enable', 'false')
             .getOrCreate()
             )

    vote_schema = StructType([
        StructField('voter_id', StringType(), True),
        StructField('candidate_id', StringType(), True),
        StructField('voting_time', TimestampType(), True),
        StructField('voter_name', StringType(), True),
        StructField('party_affiliation', StringType(), True),
        StructField('biography', StringType(), True),
        StructField('campaign_platform', StringType(), True),
        StructField('photo_url', StringType(), True),
        StructField('candidate_name', StringType(), True),
        StructField('date_of_birth', StringType(), True),
        StructField('gender', StringType(), True),
        StructField('nationality', StringType(), True),
        StructField('registration_number', StringType(), True),
        StructField('address', StructType([
            StructField('street', StringType(), True),
            StructField('city', StringType(), True),
            StructField('state', StringType(), True),
            StructField('country', StringType(), True),
            StructField('postcode', StringType(), True),
        ]), True),
        StructField('email', StringType(), True),
        StructField('phone_number', StringType(), True),
        StructField('cell_number', StringType(), True),
        StructField('picture', StringType(), True),
        StructField('registered_age', IntegerType(), True),
        StructField('vote', IntegerType(), True),
    ])

    votes_df = (spark.readStream
                .format('kafka')
                .option('kafka.bootstrap.servers', 'localhost:9092')
                .option('subscribe', 'vote_topic')
                .option('staringOffsets', 'earliest')
                .load()
                .selectExpr("CAST(value AS STRING)")
                .select(from_json(col('value'), vote_schema).alias('data'))
                .select('data.*')
                )

    votes_df = votes_df.withColumn('voting_time', col('voting_time').cast(TimestampType())) \
        .withColumn('vote', col('vote').cast(IntegerType()))
    enriched_votes_df = votes_df.withWatermark('voting_time', '1 minute')

    votes_per_candidate = enriched_votes_df.groupBy('candidate_id', 'candidate_name', 'party_affiliation', 'photo_url').agg(_sum('vote').alias('total_votes'))
    turnout_by_location = enriched_votes_df.groupBy('address.state').count().alias('total_votes')

    votes_per_candidate_to_kafka = (votes_per_candidate.selectExpr('to_json(struct(*)) AS value')
                                    .writeStream
                                    .format('kafka')
                                    .option('kafka.bootstrap.servers', 'localhost:9092')
                                    .option('topic', 'aggregated_votes_per_candidate')
                                    .option('checkpointLocation', 'D:\Workspace\pyWorkspace\pythonProject\RealtimeVoting\checkpoints\checkpoint1')
                                    .outputMode('update')
                                    .start()
                                    )

    turnout_by_location_to_kafka = (turnout_by_location.selectExpr('to_json(struct(*)) AS value')
                                    .writeStream
                                    .format('kafka')
                                    .option('kafka.bootstrap.servers', 'localhost:9092')
                                    .option('topic', 'aggregated_turnout_by_location')
                                    .option('checkpointLocation',
                                            'D:\Workspace\pyWorkspace\pythonProject\RealtimeVoting\checkpoints\checkpoint2')
                                    .outputMode('update')
                                    .start()
                                    )

    votes_per_candidate_to_kafka.awaitTermination()
    turnout_by_location_to_kafka.awaitTermination()