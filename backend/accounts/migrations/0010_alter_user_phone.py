from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("accounts", "0009_user_admin_password_reset_otp_and_more")]

    operations = [
        migrations.AlterField(
            model_name="user",
            name="phone",
            field=models.CharField(max_length=16),
        ),
    ]