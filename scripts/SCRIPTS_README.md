
### Intro.
All scripts should be written in a way that they are to be executed from the sellscale-api base directory. They are executed as follows: `./scripts/<script> [args]`

## Scripts:
* `migrate_new_enum <table_name> <column_name> <new_value>`
> Args are case sensitive! A flask db migrate is not required as this command creates the migration file.
