from unittest.mock import patch

from django.contrib.auth.models import User
from django.http import HttpRequest
from django.test import Client, TestCase, override_settings
from django.urls import resolve, reverse
from model_bakery import baker as mommy
import responses
import json
from datetime import datetime, timedelta
from pyjobs.core.models import Job, Profile, JobApplication, Country, Currency
from pyjobs.core.views import index, jobs
from pyjobs.core.forms import JobApplicationForm
import csv
import io


class HomeJobsViewsTest(TestCase):
    @patch("pyjobs.marketing.triggers.post_telegram_channel")
    @patch("pyjobs.marketing.triggers.send_group_notification")
    @patch("pyjobs.marketing.triggers.send_job_to_github_issues")
    def setUp(
        self, _mocked_send_group_push, _mock_github, _mocked_post_telegram_channel
    ):
        self.job = Job(
            title="Vaga 1",
            workplace="Sao Paulo",
            company_name="XPTO",
            application_link="http://www.xpto.com.br/apply",
            company_email="vm@xpto.com",
            description="Job bem maneiro",
        )
        self.job.save()
        self.jobs_page = resolve("/jobs/")
        self.home_page = resolve("/")
        self.request = HttpRequest()
        self.home_page_html = index(self.request).content.decode("utf-8")
        self.jobs_page_html = jobs(self.request).content.decode("utf-8")

    def test_job_is_in_websites_home(self):
        self.assertEqual(self.home_page.func, index)

    def test_job_in_home(self):
        job_title = self.job.title
        self.assertTrue(job_title in self.jobs_page_html)

    def test_job_url_is_in_home(self):
        job_url = "/job/{}/".format(str(self.job.unique_slug))
        self.assertTrue(job_url in self.jobs_page_html)


class JobDetailsViewTest(TestCase):
    @patch("pyjobs.marketing.triggers.post_telegram_channel")
    @patch("pyjobs.marketing.triggers.send_group_notification")
    @patch("pyjobs.marketing.triggers.send_job_to_github_issues")
    def setUp(
        self, _mocked_send_group_push, _mock_github, _mocked_post_telegram_channel
    ):
        self.job = Job(
            title="Vaga 1",
            workplace="Sao Paulo",
            company_name="XPTO",
            application_link="http://www.xpto.com.br/apply",
            company_email="vm@xpto.com",
            description="Job bem maneiro",
            requirements="Job bem maneiro",
            salary_range=10,
        )
        self.job.save()
        self.client = Client()
        self.job_view_html = self.client.get(
            f"/job/{self.job.unique_slug}/"
        ).content.decode("utf-8")

    def test_job_title_in_view(self):
        self.assertTrue(self.job.title in self.job_view_html)

    def test_job_workplace_in_view(self):
        self.assertTrue(self.job.workplace in self.job_view_html)

    def test_job_company_in_view(self):
        self.assertTrue(self.job.company_name in self.job_view_html)

    def test_job_application_link_not_in_view(self):
        self.assertTrue(self.job.application_link not in self.job_view_html)

    def test_job_description_in_view(self):
        self.assertTrue(self.job.description in self.job_view_html)

    def test_job_requirements_in_view(self):
        self.assertTrue(self.job.requirements in self.job_view_html)

    def test_job_status_code_is_200(self):
        status_code = self.client.get(f"/job/{self.job.unique_slug}/").status_code
        self.assertEqual(status_code, 200)


class PyJobsJobApplication(TestCase):
    @responses.activate
    @patch("pyjobs.marketing.triggers.post_telegram_channel")
    @patch("pyjobs.marketing.triggers.send_group_notification")
    @patch("pyjobs.marketing.triggers.send_job_to_github_issues")
    def setUp(
        self, _mocked_send_group_push, _mock_github, _mocked_post_telegram_channel
    ):
        responses.add(
            responses.POST,
            "https://api.mailerlite.com/api/v2/subscribers",
            json={"status": "Success"},
            status=200,
        )

        self.job = Job.objects.create(
            title="Vaga 3",
            workplace="Sao Paulo",
            company_name="XPTO",
            company_email="vm@xpto.com",
            description="Job bem maneiro",
            premium=True,
            public=True,
        )

        self.user = User.objects.create_user(
            username="jacob", email="jacob@gmail.com", password="top_secret"
        )

        self.profile = Profile.objects.create(
            user=self.user,
            github="http://www.github.com/foobar",
            linkedin="http://www.linkedin.com/in/foobar",
            portfolio="http://www.foobar.com/",
            cellphone="11981435390",
        )

        self.client = Client()

    def test_check_applied_for_job_anon(self):
        request_client = self.client.get("/job/{}/".format(self.job.unique_slug))
        request = request_client.content.decode("utf-8")
        expected_response = "Entre e Aplique a vaga!"
        self.assertTrue(expected_response in request)

    def test_check_applied_for_job(self):
        self.client.login(username="jacob", password="top_secret")
        request_client = self.client.get("/job/{}/".format(self.job.unique_slug))
        request = request_client.content.decode("utf-8")
        expected_response = "Candidate-se para esta vaga pelo"
        self.assertTrue(expected_response in request)

    def test_check_if_profile_with_no_skills_can_apply(self):
        self.client.login(username="jacob", password="top_secret")
        job_url = "/job/{}/".format(self.job.unique_slug)
        request_client = self.client.get(job_url)
        request = request_client.content.decode("utf-8")
        request_apply = self.client.post(job_url, follow=True)

        self.assertTrue(
            "Você já aplicou a esta vaga!" in request_apply.content.decode("utf-8")
        )


class PyJobsContact(TestCase):
    def setUp(self):
        self.client = Client()

    def test_check_if_is_correct_page(self):
        response = self.client.get("/contact/").content.decode("utf-8")
        self.assertTrue("Contato" in response)

    @override_settings(RECAPTCHA_SECRET_KEY="my-secret")
    def test_check_if_is_validating_the_form(self):
        response = self.client.post("/contact/", follow=True)
        content = response.content.decode("utf-8")
        self.assertTrue("Falha na hora de mandar a mensagem" in content)

    @override_settings(RECAPTCHA_SECRET_KEY=None)
    @patch("pyjobs.core.views.ContactForm")
    @responses.activate
    def test_check_if_when_recaptcha_is_none_message_is_sent(self, _mocked_form_save):
        responses.add(
            responses.POST,
            "https://www.google.com/recaptcha/api/siteverify",
            json={"success": "Success"},
            status=200,
        )
        response = self.client.post("/contact/", follow=True)
        content = response.content.decode("utf-8")
        self.assertTrue("Mensagem enviada com sucesso" in content)


class PyJobsMultipleJobsPagesTest(TestCase):
    @patch("pyjobs.marketing.triggers.post_telegram_channel")
    @patch("pyjobs.marketing.triggers.send_group_notification")
    @patch("pyjobs.marketing.triggers.send_job_to_github_issues")
    def setUp(
        self, _mocked_send_group_push, _mock_github, _mocked_post_telegram_channel
    ):
        self.country = mommy.make(Country)
        self.currency = mommy.make(Currency)
        self.job = mommy.make(
            Job, public=True, country=self.country, currency=self.currency, _quantity=20
        )
        self.client = Client()

    def test_first_page(self):
        response = self.client.get("/jobs/?page=1")
        self.assertTrue(response.status_code == 200)

    def test_second_page(self):
        response = self.client.get("/jobs/?page=2")
        self.assertTrue(response.status_code == 200)

    def test_third_page_redirection(self):
        response = self.client.get("/jobs/?page=3")
        self.assertRedirects(response, "/", status_code=302, target_status_code=200)

    def test_string_in_page_redirection(self):
        response = self.client.get("/jobs/?page=ola")
        self.assertRedirects(response, "/", status_code=302, target_status_code=200)


class PyJobsSummaryPageTest(TestCase):
    @patch("pyjobs.marketing.triggers.post_telegram_channel")
    @patch("pyjobs.marketing.triggers.send_group_notification")
    @patch("pyjobs.marketing.triggers.send_job_to_github_issues")
    def setUp(
        self, _mocked_send_group_push, _mock_github, _mocked_post_telegram_channel
    ):
        mommy.make("core.Job", _quantity=1)
        self.client = Client()

    def test_if_returns_right_status_code(self):
        response = self.client.get("/summary/")
        self.assertEqual(response.status_code, 200)

    def test_if_job_data_is_in_page(self):
        response = self.client.get("/summary/")
        first_job = Job.objects.all().first()
        self.assertContains(response, first_job.title)
        self.assertContains(response, first_job.company_name)
        self.assertContains(response, first_job.workplace)


class PyJobsFeedTest(TestCase):
    @patch("pyjobs.marketing.triggers.send_group_notification")
    @patch("pyjobs.marketing.triggers.send_job_to_github_issues")
    @patch("pyjobs.marketing.triggers.post_telegram_channel")
    def setUp(
        self, _mocked_send_group_push, _mock_github, _mocked_post_telegram_channel
    ):
        self.country = mommy.make(Country)
        self.currency = mommy.make(Currency)
        self.job = mommy.make(
            Job, public=True, country=self.country, currency=self.currency
        )
        self.client = Client()

    def test_if_feed_returns_right_status_code(self):
        response = self.client.get("/feed/")
        self.assertEqual(response.status_code, 200)

    def test_if_job_data_is_in_feed(self):
        response = self.client.get("/feed/")
        first_job = Job.objects.all().first()
        self.assertContains(response, first_job.title)
        self.assertContains(response, first_job.company_name)
        self.assertContains(response, first_job.workplace)


class PyJobsPremiumFeedTest(TestCase):
    @patch("pyjobs.marketing.triggers.send_group_notification")
    @patch("pyjobs.marketing.triggers.send_job_to_github_issues")
    @patch("pyjobs.marketing.triggers.post_telegram_channel")
    def setUp(
        self, _mocked_send_group_push, _mock_github, _mocked_post_telegram_channel
    ):
        self.country = mommy.make(Country)
        self.currency = mommy.make(Currency)
        self.job = mommy.make(
            Job, public=True, country=self.country, currency=self.currency
        )
        self.client = Client()

    def test_if_feed_returns_right_status_code(self):
        response = self.client.get("/feed/")
        self.assertEqual(response.status_code, 200)

    def test_if_job_data_is_in_feed(self):
        response = self.client.get("/feed/premium/")
        content = response.content.decode("utf-8")
        first_job = Job.objects.all().first()
        self.assertContains(response, first_job.title)
        self.assertContains(response, first_job.company_name)
        self.assertContains(response, first_job.workplace)


class PyJobsRobotsTXTTest(TestCase):
    def setUp(self):
        self.client = Client()

    def test_robots_txt_status_code(self):
        response = self.client.get("/robots.txt")
        self.assertEqual(response.status_code, 200)


class PyJobsJobCloseView(TestCase):
    @patch("pyjobs.marketing.triggers.send_group_notification")
    @patch("pyjobs.marketing.triggers.send_job_to_github_issues")
    @patch("pyjobs.marketing.triggers.post_telegram_channel")
    def setUp(
        self, _mocked_send_group_push, _mock_github, _mocked_post_telegram_channel
    ):
        self.job = Job(
            title="Vaga 1",
            workplace="Sao Paulo",
            company_name="XPTO",
            application_link="http://www.xpto.com.br/apply",
            company_email="vm@xpto.com",
            description="Job bem maneiro",
        )
        self.job.save()

    def _assert_close_link(self, kwargs, closed):
        url = reverse("close_job", kwargs=kwargs)
        response = self.client.get(url)
        if closed:
            self.assertEqual(200, response.status_code)
            self.assertEqual(0, Job.objects.filter(is_open=True).count())
        else:
            self.assertEqual(302, response.status_code)
            self.assertEqual(1, Job.objects.filter(is_open=True).count())

    def test_valid_close_view(self):
        kwargs = {
            "unique_slug": self.job.unique_slug,
            "close_hash": self.job.close_hash(),
        }
        self._assert_close_link(kwargs, closed=True)

    def test_close_view_for_non_existent_job(self):
        wrong_pk = self.job.unique_slug[:-2]
        kwargs = {"unique_slug": wrong_pk, "close_hash": self.job.close_hash()}
        self._assert_close_link(kwargs, closed=False)

    def test_close_view_with_wrong_hash(self):
        right_hash = self.job.close_hash()
        wrong_hash = right_hash[64:] + right_hash[:64]
        kwargs = {"unique_slug": self.job.unique_slug, "close_hash": wrong_hash}
        self._assert_close_link(kwargs, closed=False)


class PyJobsNormalViews(TestCase):
    def setUp(self):
        self.client = Client()

    def test_if_services_page_returns_200(self):
        response = self.client.get("/services/")
        self.assertEqual(response.status_code, 200)

    def test_if_job_creation_page_returns_200(self):
        response = self.client.get("/job/create/")
        self.assertEqual(response.status_code, 200)


class PyJobsRegisterNewJob(TestCase):
    def setUp(self):
        self.client = Client()
        invalid_data = {}
        valid_data = {
            "title": "Test",
        }

    @patch("pyjobs.marketing.triggers.send_group_notification")
    @patch("pyjobs.marketing.triggers.send_job_to_github_issues")
    @patch("pyjobs.marketing.triggers.post_telegram_channel")
    @responses.activate
    def test_if_job_register_page_returns_400(self, _mock1, _mock_github, _mock2):
        responses.add(
            responses.POST,
            "https://www.google.com/recaptcha/api/siteverify",
            json.dumps({"success": False}),
            status=200,
            content_type="application/json",
        )
        response = self.client.post("/job/create/", follow=True, data={})
        self.assertEqual(response.status_code, 400)

    @patch("pyjobs.marketing.triggers.send_group_notification")
    @patch("pyjobs.marketing.triggers.send_job_to_github_issues")
    @patch("pyjobs.marketing.triggers.post_telegram_channel")
    # @responses.activate
    def test_if_job_register_page_returns_form_error(
        self, _mock1, _mock_github, _mock2
    ):
        responses.add(
            responses.POST,
            "https://www.google.com/recaptcha/api/siteverify",
            json.dumps({"success": False}),
            status=200,
            content_type="application/json",
            match_querystring=True,
        )
        response = self.client.post(
            "/job/create/",
            data={
                "title": "",
                "skills": "",
            },
        )
        content = response.content.decode("utf-8")
        self.assertTrue("Falha na hora de criar o job" in content)

    @responses.activate
    @patch("pyjobs.core.views.JobForm")
    @patch("pyjobs.marketing.triggers.send_group_notification")
    @patch("pyjobs.marketing.triggers.send_job_to_github_issues")
    @patch("pyjobs.marketing.triggers.post_telegram_channel")
    def test_if_job_register_page_returns_success_with_recaptcha(
        self, _mock_telegram, _mock_github, _mock_push, _mocked_form
    ):
        responses.add(
            responses.POST,
            "https://www.google.com/recaptcha/api/siteverify",
            json={"success": True},
            status=200,
        )
        response = self.client.post(
            "/job/create/",
            follow=True,
            data={
                "title": "Vaga 3",
                "workplace": "Sao Paulo",
                "company_name": "XPTO",
                "company_email": "vm@xpto.com",
                "description": "Job bem maneiro",
                "premium": True,
                "public": True,
            },
        )
        content = response.content.decode("utf-8")
        self.assertTrue("Parabéns! Sua vaga foi registrada!" in content)


class PyJobsJobChallenge(TestCase):
    @patch("pyjobs.marketing.triggers.send_group_notification")
    @patch("pyjobs.marketing.triggers.send_job_to_github_issues")
    @patch("pyjobs.marketing.triggers.post_telegram_channel")
    def setUp(
        self, _mocked_send_group_push, _mock_github, _mocked_post_telegram_channel
    ):
        self.job = Job.objects.create(
            title="Vaga 3",
            workplace="Sao Paulo",
            company_name="XPTO",
            company_email="vm@xpto.com",
            description="Job bem maneiro",
            premium=True,
            public=True,
        )

        self.job.created_at = datetime.now() - timedelta(days=70)
        self.job.save()

        self.user = User.objects.create_user(
            username="jacob", email="jacob@gmail.com", password="top_secret"
        )

        self.profile = Profile.objects.create(
            user=self.user,
            github="http://www.github.com/foobar",
            linkedin="http://www.linkedin.com/in/foobar",
            portfolio="http://www.foobar.com/",
            cellphone="11981435390",
        )

        self.client = Client()

        self.client.login(username="jacob", password="top_secret")

    def test_if_job_that_is_not_challenging_redirects_to_job_page(self):
        response = self.client.get(
            "/job/{}/challenge_submit/".format(self.job.unique_slug), follow=True
        )
        url = response.redirect_chain[0][0]
        self.assertEqual(url, "/job/{}/".format(self.job.unique_slug))

    @patch("pyjobs.core.views.JobApplicationForm")
    def test_if_user_applies(self, _mocked_form):
        self.client.login(username="jacob", password="top_secret")
        self.job.is_challenging = True
        self.job.save()
        self.job.refresh_from_db()
        self.job_application = JobApplication.objects.create(
            job=self.job, user=self.user
        )
        self.job_application.refresh_from_db()
        mock_form = _mocked_form.return_value
        mock_form.is_valid.return_value = True

        response = self.client.post(
            "/job/{}/challenge_submit/".format(self.job.unique_slug),
            data={"challenge_response_link": "http://www.google.com"},
            content_type="application/x-www-form-urlencoded",
            follow=True,
        )
        mock_form.save.assert_called()

    def test_if_old_job_message_alerts(self):
        response = self.client.get(
            "/job/{}/".format(self.job.unique_slug), follow=False
        )
        content = response.content.decode("utf-8")
        self.assertIn("Confirme com a empresa sobre a disponbilidade!", content)


class AppliedUsersDetailsTest(TestCase):
    @patch("pyjobs.marketing.triggers.send_group_notification")
    @patch("pyjobs.marketing.triggers.send_job_to_github_issues")
    @patch("pyjobs.marketing.triggers.post_telegram_channel")
    def setUp(self, _mock1, _mock_github, _mock2):
        self.job = Job.objects.create(
            title="Vaga 3",
            workplace="Sao Paulo",
            company_name="XPTO",
            company_email="vm@xpto.com",
            description="Job bem maneiro",
            premium=True,
            public=True,
        )

        self.user = User.objects.create_user(
            username="jacob",
            first_name="jacob",
            last_name="bocaj",
            email="jacob@gmail.com",
            password="top_secret",
            is_staff=True,
        )

        self.profile = Profile.objects.create(
            user=self.user,
            github="http://www.github.com/foobar",
            linkedin="http://www.linkedin.com/in/foobar",
            portfolio="http://www.foobar.com/",
            cellphone="11981435390",
        )

        self.job_application = JobApplication.objects.create(
            user=self.user, job=self.job
        )

        self.client = Client()

        self.client.login(username="jacob", password="top_secret")

    def test_if_job_application_is_in_page(self):
        response = self.client.get("/job/{}/details/".format(self.job.unique_slug))
        content = response.content.decode("utf-8")
        self.assertIn(self.user.first_name, content)
        self.assertIn(self.user.last_name, content)
        self.assertIn(self.profile.github, content)

    def test_if_get_job_applications_page_works(self):
        response = self.client.get("/job/{}/app/".format(self.job.unique_slug))
        content = response.content.decode("utf-8")
        csv_reader = csv.reader(io.StringIO(content))
        body = list(csv_reader)

        self.assertEqual(response.status_code, 200)
        self.assertIn(self.user.first_name, body[1])

    def test_if_get_job_applications_feedback_page_works(self):
        response = self.client.get(
            "/job/application/{}/".format(self.job_application.pk)
        )
        content = response.content.decode("utf-8")
        self.assertTrue(response.status_code == 200)

    def test_if_get_job_applications_feedback_sends_feedback(self):
        response = self.client.post(
            "/job/application/{}/".format(self.job_application.pk),
            data={
                "company_feedback": "Teste",
                "company_feedback_type": 1,
            },
        )
        content = response.content.decode("utf-8")
        self.assertIn("Feedback enviado para:", content)


class JobApplicationDetailsWithoutLoginTest:
    def setUp(self):
        self.client = Client()

    def test_if_application_details_are_not_available_for_wrong_users(self):
        response = self.client.get("/job/{}/details".format(self.job.unique_slug))
        self.assertEqual(response.status_code, 301)
